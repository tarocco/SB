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
        self._active_drawables = set()

    def get_root_transforms(self):
        return self._root_transform.children

    def add_root_transform(self, xform):
        xform.parent = self._root_transform

    def find_components(self, component_type):
        for xf in self._root_transform.descendants:
            yield from xf.get_object().get_components(component_type)

    def _get_mst_set(self, transforms):
        visited = set()
        for xf in transforms:
            t = xf
            while t and t not in visited:
                visited.add(t)
                t = t.parent
        return visited

    def update(self, dt):
        self._root_transform.width = self.width
        self._root_transform.height = self.height

        transforms = self._root_transform.descendants

        lut = self._root_transform.descendant_hierarchy
        data = np.empty((len(transforms), 2), dtype='float32')
        transform_model_calc(transforms, lut)


        all_removed = set()
        removal = list()
        removal_parents = list()

        for xf in transforms:
            _object = xf.get_object()
            if not xf.parent in all_removed:
                drawables = _object.get_components(Drawable)
                if _object.alive:
                    for drawable in drawables:
                        if drawable not in self._active_drawables:
                            drawable._add_to_canvas(self.canvas)
                            self._active_drawables.add(drawable)
                    _object.update_components(dt)
                else:
                    removal.append(xf)
                    removal_parents.append(xf.parent)
                    all_removed.add(xf)
                    for drawable in drawables:
                        if drawable in self._active_drawables:
                            drawable._remove_from_canvas(self.canvas)
                            self._active_drawables.remove(drawable)
            else:
                all_removed.add(xf)

        clear = self._get_mst_set(removal_parents)

        for xf in clear:
            xf._clear_descendants()

        for xf in removal:
            xf._parent._children.remove(xf)
            xf._clear_descendants()
            xf._parent = None