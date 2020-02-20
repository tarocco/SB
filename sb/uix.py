from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scatterlayout import ScatterLayout
from kivy.properties import AliasProperty, \
    ReferenceListProperty, \
    NumericProperty, \
    BoundedNumericProperty
from kivy.graphics.transformation import Matrix
from kivy.graphics import ScissorPush, ScissorPop
from kivy.clock import Clock
import numpy as np

from sb.animation import PointRelaxer

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
        # Slight hack but it should work
        app = App.get_running_app()
        self.running_app = app
        app.bind(on_start=self.on_app_start)
        app.bind(on_stop=self.on_app_stop)
        self._target_widget_pos_hints = None
        self._prior_widget_pos_hints = None
        self._point_relaxer = PointRelaxer()

    def set_point_relaxer(self, point_relaxer):
        self._point_relaxer = point_relaxer

    def get_widgets(self):
        return self._inner_content.children

    def get_widget_pos_hints(self):
        widgets = self._inner_content.children
        return np.array([(w.pos_hint.get('x') or 0, w.pos_hint.get('y') or 0)
                         for w in widgets])

    def set_widget_pos_hints(self, widgets, pos_hints):
        for w, h in zip(widgets, pos_hints):
            w.pos_hint = {'x': float(h[0]), 'y': float(h[1])}

    def set_cached_widget_pos_hints(self, indices, pos_hints):
        if self._target_widget_pos_hints is None:
            self._target_widget_pos_hints = self.get_widget_pos_hints()
            self._point_relaxer.set_points(self._target_widget_pos_hints)
        self._target_widget_pos_hints[indices, ...] = pos_hints[:, ...]

    def _validate_widget_pos_hint_cache(self):
        if self._target_widget_pos_hints is None:
            self._target_widget_pos_hints = self.get_widget_pos_hints()
            self._point_relaxer.set_points(self._target_widget_pos_hints)
        if self._prior_widget_pos_hints is None:
            self._prior_widget_pos_hints = self._target_widget_pos_hints.copy()

    def _update_widgets(self, dt):
        self._validate_widget_pos_hint_cache()
        self._target_widget_pos_hints = self._point_relaxer.get_points()
        a = self._prior_widget_pos_hints
        b = self._target_widget_pos_hints
        try:
            self._prior_widget_pos_hints = a + (b - a) * 4 * dt
            widgets = self.get_widgets()
            self.set_widget_pos_hints(widgets, self._prior_widget_pos_hints)
        except:
            pass

    def on_app_start(self, src):
        Clock.schedule_interval(self._update_widgets, 1/60)
        self._point_relaxer.init_processes(1000)
        self._point_relaxer.start_all()
        self._validate_widget_pos_hint_cache()
        self._point_relaxer.set_points(self._target_widget_pos_hints)

    def on_app_stop(self, src):
        self._point_relaxer.stop_all()

    def add_widget(self, widget, index=0, canvas=None):
        self._inner_content.add_widget(widget, index, canvas)
        self._target_widget_pos_hints = None
        self._prior_widget_pos_hints = None

    def remove_widget(self, widget, index=0, canvas=None):
        self._inner_content.remove(widget)
        self._target_widget_pos_hints = None
        self._prior_widget_pos_hints = None

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
