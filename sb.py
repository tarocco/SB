import sys
from os import path, walk
import pathlib
import io
import shutil

from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scatterlayout import ScatterLayout
from kivy.uix.image import Image as kImage, CoreImage
from kivy.properties import AliasProperty, \
    ReferenceListProperty, \
    NumericProperty, \
    BoundedNumericProperty
from kivy.graphics.transformation import Matrix
from kivy.graphics import ScissorPush, ScissorPop
from PIL import Image as PILImageM
from PIL.Image import Image as PILImage
import numpy as np
from itertools import islice

import pytess
from scipy.spatial import KDTree
from scipy.special import softmax

from argparse import ArgumentParser


def get_image_paths(parent_path):
    suffixes = {'png', 'jpg', 'gif', 'webp'}
    for root, dirs, files in walk(parent_path):
        for file in files:
            name, ext = path.splitext(file)
            if ext[1:].lower() in suffixes:
                yield pathlib.PurePath(root, file)


def prepare_thumbnails(image_paths, thumbnails_path):
    if not image_paths:
        return
    if isinstance(thumbnails_path, str):
        thumbnails_path = pathlib.Path(thumbnails_path)
    for image_path in image_paths:
        assert(isinstance(image_path, pathlib.PurePath))
        title, ext = path.splitext(image_path.name)
        thumbnail_name = 'thumbnail-' + title + '.png'
        thumbnail_path = thumbnails_path.joinpath(thumbnail_name)
        if thumbnail_path.exists():
            # Load thumbnail image
            with open(thumbnail_path, 'rb') as thumbnail_file:
                thumbnail_io = io.BytesIO(thumbnail_file.read())
            thumbnail_io.seek(0)
            img = PILImageM.open(thumbnail_io)
            thumbnail_io.seek(0)
        else:
            # Generate thumbnail image
            img = PILImageM.open(str(image_path))
            assert(isinstance(img, PILImage))
            img.thumbnail((64, 64))
            thumbnail_io = io.BytesIO()
            img.save(thumbnail_io, 'PNG')
            thumbnail_io.seek(0)
            # Caching handled by Kivy
            with open(thumbnail_path, 'wb') as thumbnail_file:
                shutil.copyfileobj(thumbnail_io, thumbnail_file)
            thumbnail_io.seek(0)

        yield thumbnail_path, thumbnail_io, img


class Analysis:
    def __init__(self, mean, contrast):
        self.mean = mean
        self.contrast = contrast

    @classmethod
    def process_image(cls, img):
        if isinstance(img, np.ndarray):
            array = img
        elif isinstance(img, PILImage):
            array = np.array(img) / 255.0
        else:
            raise ValueError("img must be a supported type")
        flat = array.flatten()
        mean = np.sum(flat) / flat.size
        contrast = np.sum(np.abs(flat - mean)) / flat.size
        return Analysis(mean, contrast)

    def __repr__(self):
        return f'<Analysis mean = {self.mean}, contrast = {self.contrast}>'


class SBView(FloatLayout):
    def __init__(self, **kwargs):
        super(SBView, self).__init__(**kwargs)
        self.scatter = SBScatter(id='scatter')
        self.scatter.size_hint = (None, None)
        super().add_widget(self.scatter)
        self.bind(width=self.width_changed)
        self.bind(height=self.height_changed)
        self._prior_width = None
        self._prior_height = None

        # Set and forget
        with self.canvas.after:
            ScissorPop()

    def _update_clipping_mask(self):
        self.canvas.before.clear()
        with self.canvas.before:
            x, y = self.to_window(*self.pos)
            width, height = self.size
            ScissorPush(x=int(round(x)), y=int(round(y)),
                        width=int(round(width)), height=int(round(height)))

    def width_changed(self, src, value):
        self._update_clipping_mask()
        if self._prior_width:
            difference = value - self._prior_width
            self.scatter.x += difference * self.pivot_x
        self._prior_width = value

    def height_changed(self, src, value):
        self._update_clipping_mask()
        if self._prior_height:
            difference = value - self._prior_height
            self.scatter.y += difference * self.pivot_y
        self._prior_height = value

    def add_widget(self, widget, index=0, canvas=None):
        self.scatter.add_widget(widget, index, canvas)

    def remove_widget(self, widget, index=0, canvas=None):
        self.scatter.remove(widget)

    pivot_x = BoundedNumericProperty(0.5, min=0.0, max=1.0, bind=['width'])
    pivot_y = BoundedNumericProperty(0.5, min=0.0, max=1.0, bint=['height'])
    pivot = ReferenceListProperty(pivot_x, pivot_y)


class SBScatter(ScatterLayout):
    def __init__(self, **kwargs):
        super(SBScatter, self).__init__(**kwargs)
        inner_content = FloatLayout()
        inner_content.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
        inner_content.size_hint = (0.5, 0.5)
        super().add_widget(inner_content)
        self._inner_content = inner_content

    def add_widget(self, widget, index=0, canvas=None):
        self._inner_content.add_widget(widget, index, canvas)

    def remove_widget(self, widget, index=0, canvas=None):
        self._inner_content.remove(widget)

    def _set_scale(self, scale, anchor=(0.5, 0.5)):
        rescale = scale * 1.0 / self.scale
        mtx = Matrix().scale(rescale, rescale, rescale)
        self.apply_transform(mtx, anchor=anchor)

    def on_touch_down(self, touch):
        if touch.is_mouse_scrolling:
            if touch.button == 'scrolldown':
                s = self.scale * self.scroll_zoom_rate
            elif touch.button == 'scrollup':
                s = self.scale / self.scroll_zoom_rate
            else:
                s = None
            if s and self.scale_min <= s <= self.scale_max:
                self._set_scale(s, touch.pos)
        super().on_touch_down(touch)

    scroll_zoom_rate = NumericProperty(1.1)
    scale = AliasProperty(ScatterLayout._get_scale, _set_scale,
                          bind=('x', 'y', 'transform'))


def get_abs_path(path):
    assert(isinstance(path, pathlib.PurePath))
    if path.is_absolute():
        return path
    return pathlib.Path.cwd().joinpath(path)


def get_path_uri(path):
    assert (isinstance(path, pathlib.PurePath))
    return get_abs_path(path).as_uri()


class SBApp(App):
    def __init__(self):
        super(SBApp, self).__init__()
        self.images = None
        self.coordinates = None

    def on_start(self):
        view = self.root.ids.scatter_view
        assert(isinstance(view, SBView))
        n_images = len(self.images)
        kimages = [kImage() for _ in range(n_images)]
        for kimg, img, c in zip(kimages, self.images, self.coordinates):
            view.add_widget(kimg)
            kimg.texture = img.texture
            kimg.size_hint = (None, None)
            kimg.size = tuple(0.1 * i for i in kimg.texture_size)
            kimg.pos_hint = {'x': float(c[0]), 'y': float(c[1])}
        view.size = view.parent.size
        view.scatter.size = view.size


def relax_points(points):
    voronois = pytess.voronoi(points)
    _, polys = list(zip(*voronois))
    return [np.apply_along_axis(np.mean, 0, np.array(v)) for v in polys]


def k_relax_points(points, alpha, beta, k=3):
    """
    Relax points by alpha strength to objective beta distance
    by k-nearest points
    :param points: (list of 1d array-like) vectors to relax
    :param alpha: (float) iteration strength
    :param beta: (float) target point distance/spacing
    :return: (list of 1d array-like) relaxed vectors
    """
    kdt = KDTree(points)
    relaxed = []
    for p in points:
        q = kdt.query(p, k=k + 1)
        distances, indices = q
        data = zip(distances, indices)
        next(data)  # Skip self
        p2 = np.array(p)
        for d, i in data:
            if i not in range(len(kdt.data)):
                continue
            n = np.array(kdt.data[i]) - p2
            n = n / (np.linalg.norm(n) + 0.0001)
            s = (d - beta)
            p2 = p2 + alpha * s * n
        relaxed.append(p2)
    return relaxed


def main():
    parser = ArgumentParser()
    parser.add_argument('--images', type=str)
    parser.add_argument('--thumbnail-images', type=str)
    args = parser.parse_args()

    thumbnails_path = pathlib.Path(args.thumbnail_images)
    thumbnails_path.mkdir(parents=True, exist_ok=True)
    thumbnails = list(prepare_thumbnails(
        get_image_paths(args.images),
        thumbnails_path))

    thumbnail_paths, thumbnail_ios, thumbnail_images = zip(*thumbnails)
    analyses = list(map(Analysis.process_image, thumbnail_images))
    points = [(a.mean, a.contrast) for a in analyses]

    for _ in range(4):
        points = k_relax_points(points, 0.2, 0.07, 6)

    for _ in range(32):
        points = k_relax_points(points, 0.1, 0.05, 3)

    # Reset stream positions after generating analyses (PIL affects it)
    for thumb_io in thumbnail_ios:
        thumb_io.seek(0)

    imgs = [CoreImage(thumb_io, ext='png', filename=str(thumb_path))
             for thumb_io, thumb_path in zip(thumbnail_ios, thumbnail_paths)]

    # Free some memory
    del thumbnail_images

    app = SBApp()
    app.images = imgs
    app.coordinates = points
    app.run()


if __name__ == '__main__':
    main()