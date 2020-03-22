from kivy.uix.widget import Widget
import numpy as np

from sb.sbobject import SBObject
from sb.drawable import Drawable
from sb.recttransform import transform_model_calc


class SBCanvas(Widget):
    def __init__(self, *args, **kwargs):
        super(SBCanvas, self).__init__(*args, **kwargs)
        self._root_object = SBObject()
        self._root_transform = self._root_object.transform

    def get_root_transforms(self):
        return self._root_transform.children

    def add_root_transform(self, xform):
        xform.parent = self._root_transform

    def find_components(self, component_type):
        for xf in self._root_transform.descendants:
            yield from xf.get_object().get_components(component_type)

    def update(self, dt):
        self._root_transform.width = self.width
        self._root_transform.height = self.height

        transforms = self._root_transform.descendants
        lut = self._root_transform.hierarchy
        data = np.empty((len(transforms), 2), dtype='float32')
        transform_model_calc(transforms, lut)
        for t in self._root_transform.descendants:
            _object = t.get_object()
            _object.update_components(dt)
            drawables = _object.get_components(Drawable)
            for drawable in drawables:
                drawable._add_to_canvas(self.canvas)
