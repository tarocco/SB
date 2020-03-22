import numpy as np
from ekstrakto.helpers import peak_find_3d
from PIL.Image import Image as PILImage
from sklearn.decomposition import KernelPCA


class Analysis:
    def __init__(self, mean, contrast, *args, **kwargs):
        self.mean = mean
        self.contrast = contrast
        self.colors = kwargs.get('colors')

    @classmethod
    def process_image(cls, img):
        if isinstance(img, np.ndarray):
            array = img
        elif isinstance(img, PILImage):
            array = np.concatenate(np.array(img)) / 255.0
        else:
            raise ValueError("img must be a supported type")

        # Add channel dimension
        if len(array.shape) < 2:
            array = array[..., None]
        # Remove extra channels
        if array.shape[1] > 3:
            array = array[..., :3]
        # Replace missing channels
        elif array.shape[1] < 3:  # TODO
            fill = np.tile(array[..., -1, None], 3 - array.shape[1])
            array = np.concatenate((array, fill), 1)

        flat = array.flatten()
        mean = np.sum(flat) / flat.size
        contrast = np.sum(np.abs(flat - mean)) / flat.size

        # Calculate dominant colors
        colors, _ = peak_find_3d(array, 7, 2.0)
        n_colors = 3
        if colors.shape[0] < n_colors:
            fill = np.repeat([colors[-1]], n_colors - colors.shape[0], axis=0)
            colors = np.concatenate((colors, fill), 0)

        return Analysis(mean, contrast, colors=colors)

    def get_data(self):
        return [self.mean, self.contrast, *self.colors[:3].flatten()]

    def __repr__(self):
        return f'<Analysis mean = {self.mean}, contrast = {self.contrast}>'


def process_batch_analysis_to_2d(analyses):
    data = np.array([a.get_data() for a in analyses])
    # D reduction
    pca = KernelPCA(n_components=2)
    return pca.fit_transform(data)
