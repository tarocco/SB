from kivy.uix.widget import Widget
from sb.recttransform import RectTransform
from kivy.graphics import \
    Color, Rectangle

from sb.component import Component
from sb.sbobject import SBObject
from sb.util import walk_transforms

from kivy.uix.floatlayout import FloatLayout


class Drawable(Component):
    def _add_to_canvas(self, canvas):
        pass

    def _remove_from_canvas(self, canvas):
        pass


class Image(Drawable):
    def __init__(self, _object, *args, **kwargs):
        super(Image, self).__init__(_object)
        self.texture = kwargs.get('texture', None)
        self.rectangle = Rectangle()
        self._active_canvases = set()

    def _add_to_canvas(self, canvas):
        if not self._is_active_canvas(canvas):
            canvas.add(self.rectangle)
            self._active_canvases.add(canvas)

    def _remove_from_canvas(self, canvas):
        if self._is_active_canvas(canvas):
            canvas.remove(self.rectangle)
            self._active_canvases.remove(canvas)

    def _is_active_canvas(self, canvas):
        return canvas in self._active_canvases

    def update(self, dt):
        if self.rectangle.texture != self.texture:
            self.rectangle.texture = self.texture
        self.rectangle.pos = (self.transform.x, self.transform.y)
        size = (self.transform.width, self.transform.height)
        if self.rectangle.size != size:
            self.rectangle.size = size


class SBCanvas(Widget):
    def __init__(self, *args, **kwargs):
        super(SBCanvas, self).__init__(*args, **kwargs)
        self._root_object = SBObject()
        self._root_transform = self._root_object.transform

    def get_root_transforms(self):
        return self._root_transform.children

    def add_root_transform(self, xform):
        xform.parent = self._root_transform

    def update(self, dt):
        self._root_transform.width = self.width
        self._root_transform.height = self.height
        for t in walk_transforms(self._root_transform):
            _object = t.get_object()
            _object.update_components(dt)
            drawables = _object.get_components(Drawable)
            for drawable in drawables:
                drawable._add_to_canvas(self.canvas)

