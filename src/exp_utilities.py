from sharpness.metric_list import metric_f, single_metrics
from sharpness import compute_metric_locally
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm

from time import perf_counter


def apply_transforms(input, transforms, parameters, labels, base_label):
    '''
    Computes a number of transforms of a single input.

    Parameters
    ----------
    input : np.ndarray
        Input 2-dimensional array that is to be transformed
    transforms : list
        List of transforms to apply. Each should be in the same format as those in
        sharpness.transforms, e.g., the transform is a class with parameters set on
        creation with a __call__ method that takes in and returns 2-dimensional 
        np.ndarrays.
    parameters : list
        List of parameter dictionaries for transforms. Must be the same length as
        transforms. Each element of the list must be a dictionary containing all the
        parameters needed for the corresponding transform.
    labels : list
        List of strings used to describe the transform/parameter combinations. Must
        be the same length as transforms and parameters.
    base_label : string
        Descriptive text for input.

    Returns
    -------
    result : dictionary
        Dictionary containing the following key:value pairs:
            base_label: input
            labels[i]: transforms[i](parameters[i])(input) for each i
    '''
    assert len(transforms) == len(parameters) == len(labels), 'Transforms, parameters, and labels must all be the same length'

    print('Computing transforms...')
    # Initialize dictionary with input
    result = {base_label: input}

    for i in tqdm(range(len(transforms))):
        result[labels[i]] = transforms[i](**parameters[i])(input)

    return result


def compute_metrics(inputs, metrics, plot_title=None, outdir='../media/', filename=None, plot=True, return_vals=True, uni_ratios=True):
    '''
    Computes and optionally plots metrics across a set of inputs.

    Parameters
    ----------
    inputs : dictionary
        Dictionary containing key:value pairs of the form
            descriptive text: input
        where each input should be an np.ndarry. The first input in the dictionary
        will be assumed to be the "base input" for comparison purposes, and its
        descriptive text will be used in generating the filename to save the plot to.
    metrics : list
        List of metrics to compute on all inputs. Elements of the list should be
        strings that are keys in sharpness.metric_list.metric_f.
    plot_title : string
        Optional title to display on plot.
    outdir : string
        Prefix for which directory to save the output plot to. Can be an absolute
        or relative path.
    filename : string
        Optional filename that will override the default naming scheme.
    plot : boolean
        If true, a plot will be generated, displayed, and saved.
    return_vals : boolean
        If true, the function will return summary_stats.
    uni_ratios : boolean
        If true, univariate metrics will have an additional set of statistics computed
        and displayed on the created plot. These relative min, mean, and max are the
        min, mean, and max for that particular input divided by the corresponding min,
        mean, and max values for the same metric on the "base input".

    Returns
    -------
    summary_stats : dictionary
        Dictionary with a key for each row in the plot: "intensity" corresponds to the first
        row, while each metric has its own key. The value for each key is a np.ndarray
        with columns corresponding to the columns in the plot, and rows corresponding to
        minimum, mean, and maximum values (as displayed below each image in the plot)
        respectively.
    '''

    assert set(metrics) - set(metric_f) == set(), f'Unknown metric detected in metrics: {set(metrics) - set(metric_f)}'

    print('Computing heatmaps for ' + ', '.join(metrics))
    print('on ' + ', '.join(inputs.keys()))

    base_input = list(inputs.values())[0]
    summary_stats = {'intensity': np.zeros((3, len(inputs))), **{metric: np.zeros((3, len(inputs))) for metric in metrics}}

    # Compute statistics for the first row of inputs
    for j, img in enumerate(inputs.values()):
        summary_stats['intensity'][0, j] = np.nanmin(img)
        summary_stats['intensity'][1, j] = np.nanmean(img)
        summary_stats['intensity'][2, j] = np.nanmax(img)

    if plot:  # Set up plot and plot first row of inputs
        ncols = len(inputs.keys())
        nrows = len(metrics) + 1

        F, ax = plt.subplots(ncols=ncols, nrows=nrows,
                             figsize=(ncols*4, nrows*4),
                             sharex='col', sharey='row')

        # Set up common scaling for first row
        imgs_cmin, imgs_cmax = np.nanmin(list(inputs.values())), np.nanmax(list(inputs.values()))

        for j, key in enumerate(inputs.keys()):
            my_plot = ax[0, j].imshow(inputs[key], clim=(imgs_cmin, imgs_cmax), cmap='gray', origin='lower')
            ax[0, j].set_title(key)
            ax[0, j].set_xlabel(
                f'Min: {summary_stats["intensity"][0, j]:.2f}  '
                f'Mean: {summary_stats["intensity"][1, j]:.2f}  '
                f'Max:{summary_stats["intensity"][2, j]:.2f}'
            )
            ax[0, j].set_xticks([])
            ax[0, j].set_yticks([])
            plt.colorbar(my_plot, shrink=0.7, ax=ax[0, j])

    print('\n##############################')

    for i, metric in enumerate(metrics, start=1):

        print(f'\nComputing {metric}')

        heatmaps = []
        verbosity = True if i == 1 else False  # Only print heatmap size for first metric

        # Metric computation occurs here
        start_time = perf_counter()
        for img in inputs.values():
            heatmaps.append(compute_metric_locally(base_input, img, metric, verbose=verbosity))
        comp_time = perf_counter() - start_time
        print(f'Done! {len(inputs.keys())} inputs took {comp_time} seconds')

        row_cmin = np.nanmin(heatmaps)
        row_cmax = np.nanmax(heatmaps)

        # Univariate metrics output a tuple, so just take the second element of the list
        # This works even for the fist column, because both X and T are base_input
        if metric in single_metrics:
            heatmaps = [heatmap[1] for heatmap in heatmaps]

        summary_stats[metric][0, :] = [np.nanmin(heatmap) for heatmap in heatmaps]
        summary_stats[metric][1, :] = [np.nanmean(heatmap) for heatmap in heatmaps]
        summary_stats[metric][2, :] = [np.nanmax(heatmap) for heatmap in heatmaps]

        if (metric in single_metrics) and uni_ratios:
            relative_stats = np.ndarray((3, len(inputs) - 1))
            relative_stats[0, :] = [min/summary_stats[metric][0, 0] for min in summary_stats[metric][0, 1:]]
            relative_stats[1, :] = [mean/summary_stats[metric][1, 0] for mean in summary_stats[metric][1, 1:]]
            relative_stats[2, :] = [max/summary_stats[metric][2, 0] for max in summary_stats[metric][2, 1:]]
            append_strings = ['']
            for k in range(relative_stats.shape[1]):
                append_strings.append(
                    f'\nRelative Min: {relative_stats[0, k]:.2f}  '
                    f'Mean: {relative_stats[1, k]:.2f}  '
                    f'Max: {relative_stats[2, k]:.2f}'
                )
        else:
            append_strings = ['']*len(inputs)

        if plot:
            for j, key in enumerate(inputs.keys()):
                my_plot = ax[i, j].imshow(heatmaps[j], clim=(row_cmin, row_cmax), cmap='Greens', origin='lower')
                ax[i, j].set_title(f'Heatmap - {metric} - {key}')
                ax[i, j].set_xlabel(
                    f'Min: {summary_stats[metric][0, j]:.2f}  '
                    f'Mean: {summary_stats[metric][1, j]:.2f}  '
                    f'Max: {summary_stats[metric][2, j]:.2f}' +
                    append_strings[j]
                )
                ax[i, j].set_xticks([])
                ax[i, j].set_yticks([])
                plt.colorbar(my_plot, shrink=0.7, ax=ax[i, j])

    print('\n##############################\n')

    if plot:
        print('Plotting figure...\n')
        F.suptitle(plot_title)
        plt.tight_layout()
        plt.show()
        if filename is None:
            base_name = list(inputs.keys())[0].replace(' ', '_')
            output_filename = outdir + base_name + '_' + str(len(metrics)) + '_metrics_plots.pdf'
        else:
            output_filename = filename
        print(f'\nSaving results to {output_filename}')
        F.savefig(output_filename)

    if return_vals:
        return summary_stats
