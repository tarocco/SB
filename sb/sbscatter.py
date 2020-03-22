from kivy.app import App
from kivy.uix.scatterlayout import ScatterLayout
from kivy.properties import AliasProperty, NumericProperty
from kivy.graphics.transformation import Matrix
from kivy.clock import Clock
import numpy as np

from sb.animation import PointRelaxer
from sb.sbcanvas import SBCanvas
import time


class SBScatter(ScatterLayout):
    def __init__(self, **kwargs):
        super(SBScatter, self).__init__(**kwargs)
        inner_content = SBCanvas()
        inner_content.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
        inner_content.size_hint = (0.5, 0.5)
        super().add_widget(inner_content)
        self._inner_content = inner_content

    @property
    def inner_content(self):
        return self._inner_content

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
