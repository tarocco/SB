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
        # Slight hack but it should work
        app = App.get_running_app()
        self.running_app = app
        app.bind(on_start=self.on_app_start)
        app.bind(on_stop=self.on_app_stop)
        self._target_anchors = None
        self._prior_anchors = None
        self._point_relaxer = PointRelaxer()
        self._update_widgets_iter = None

        # Debugging
        self._update_time_accumulator = 0
        self._update_anchors_accumulator = 0
        self._update_transforms_accumulator = 0
        self._update_inner_content_accumulator = 0
        self._update_number_accumulator = 0

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
        begin_t = time.process_time()

        self._validate_cached_anchors()
        points = self._point_relaxer.get_points()
        self._target_anchors = points
        a = self._prior_anchors
        b = self._target_anchors
        self._prior_anchors = a + (b - a) * min(2 * dt, 1)

        self._update_anchors_accumulator += time.process_time() - begin_t

        xform_t = time.process_time()
        xforms = self.get_root_transforms()
        anchors = self._prior_anchors
        self.set_transform_anchors(xforms, anchors)
        self._update_transforms_accumulator += time.process_time() - xform_t

        innter_content_t = time.process_time()
        self._inner_content.update(dt)
        self._update_inner_content_accumulator += time.process_time() - innter_content_t

        self._update_time_accumulator += time.process_time() - begin_t
        self._update_number_accumulator += 1

    def debug_info_update(self, dt):
        if self._update_number_accumulator > 0:
            average_update_time = self._update_time_accumulator / \
                                  self._update_number_accumulator
            average_anchor_time = self._update_anchors_accumulator / \
                                  self._update_number_accumulator
            average_xform_time = self._update_transforms_accumulator / \
                                 self._update_number_accumulator
            average_inner_content_time = \
                self._update_inner_content_accumulator / \
                self._update_number_accumulator
            print(f'Average update times (seconds):')
            print(f'{"anchors":<20s} {average_anchor_time:<0.6f}')
            print(f'{"transforms":<20s} {average_xform_time:<0.6f}')
            print(f'{"inner content":<20s} {average_inner_content_time:<0.6f}')
            print(f'{"all":<20s} {average_update_time:<0.6f}')
            self._update_anchors_accumulator = 0
            self._update_transforms_accumulator = 0
            self._update_inner_content_accumulator = 0
            self._update_time_accumulator = 0
            self._update_number_accumulator = 0

    def on_app_start(self, src):
        Clock.schedule_interval(self.update, 1/60)
        Clock.schedule_interval(self.debug_info_update, 1)
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
