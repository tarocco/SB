from iteration_utilities._iteration_utilities import grouper
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
from sb.sbcanvas import SBCanvas


class SBView(FloatLayout):
    def __init__(self, **kwargs):
        super(SBView, self).__init__(**kwargs)
        self.scatter = SBScatter()
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
        inner_content = SBCanvas()
        inner_content.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
        inner_content.size_hint = (0.5, 0.5)
        super().add_widget(inner_content)
        self._inner_content = inner_content
        # Slight hack but it should work
        app = App.get_running_app()
        self.running_app = app
        app.bind(on_start=self.on_app_start)
        app.bind(on_stop=self.on_app_stop)
        self._target_anchors = None
        self._prior_anchors = None
        self._point_relaxer = PointRelaxer()
        self._update_widgets_iter = None

    def set_point_relaxer(self, point_relaxer):
        self._point_relaxer = point_relaxer

    def get_root_transforms(self):
        return self._inner_content.get_root_transforms()

    def add_root_transform(self, xform):
        return self._inner_content.add_root_transform(xform)

    def get_all_anchors(self):
        xforms = self._inner_content._root_object.transform.children
        anchors = [(t.x_anchor, t.y_anchor) for t in xforms]
        return np.array(anchors)

    def set_transform_anchors(self, xforms, anchors):
        for t, a in zip(xforms, anchors):
            t.x_anchor, t.y_anchor = a

    def set_target_anchors(self, anchors):
        anchors = np.array(anchors)
        self._target_anchors = anchors
        self._prior_anchors = anchors.copy()
        self._point_relaxer.set_points(anchors)

    def _validate_cached_anchors(self):
        if self._target_anchors is None:
            anchors = self.get_all_anchors()
            self.set_target_anchors(anchors)
        elif self._prior_anchors is None:
            self._prior_anchors = self._target_anchors.copy()

    def update(self, dt):
        self._validate_cached_anchors()
        points = self._point_relaxer.get_points()
        self._target_anchors = points
        a = self._prior_anchors
        b = self._target_anchors
        self._prior_anchors = a + (b - a) * min(8 * dt, 1)

        xforms = self.get_root_transforms()
        anchors = self._prior_anchors
        self.set_transform_anchors(xforms, anchors)
        self._inner_content.update(dt)

    def on_app_start(self, src):
        Clock.schedule_interval(self.update, 1/60)
        self._point_relaxer.init_processes(8000)
        self._point_relaxer.start_all()
        self._validate_cached_anchors()
        self._point_relaxer.set_points(self._target_anchors)

    def on_app_stop(self, src):
        self._point_relaxer.stop_all()

    def add_widget(self, widget, index=0, canvas=None):
        self._inner_content.add_widget(widget, index, canvas)
        self._target_anchors = None
        self._prior_anchors = None

    def remove_widget(self, widget, index=0, canvas=None):
        self._inner_content.remove(widget)
        self._target_anchors = None
        self._prior_anchors = None

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
