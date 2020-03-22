from kivy.app import App
import numpy as np
import time
from kivy.clock import Clock
from sb.animation import PointRelaxer


class SBController:
    def __init__(self, sb_canvas, *args, **kwargs):
        self._sb_canvas = sb_canvas

        # Anchors
        self._target_anchors = None
        self._prior_anchors = None
        self._point_relaxer = PointRelaxer()
        self._update_widgets_iter = None

        # Debugging
        self._update_time_accumulator = 0
        self._update_anchors_accumulator = 0
        self._update_transforms_accumulator = 0
        self._update_sb_canvas_accumulator = 0
        self._update_number_accumulator = 0

    def on_app_start(self):
        Clock.schedule_interval(self.update, 1/60)
        # Clock.schedule_interval(self.debug_info_update, 1)
        self._point_relaxer.init_processes(8000)
        self._point_relaxer.start_all()
        self._validate_cached_anchors()
        self._point_relaxer.set_points(self._target_anchors)

    def on_app_stop(self):
        self._point_relaxer.stop_all()

    def set_point_relaxer(self, point_relaxer):
        self._point_relaxer = point_relaxer

    def get_root_transforms(self):
        return self._sb_canvas.get_root_transforms()

    def _get_all_anchors(self):
        xforms = self._sb_canvas._root_object.transform.children
        anchors = [(t.x_anchor, t.y_anchor) for t in xforms]
        return np.array(anchors)

    def set_target_anchors(self, anchors):
        anchors = np.array(anchors)
        self._target_anchors = anchors
        self._prior_anchors = anchors.copy()
        self._point_relaxer.set_points(anchors)

    def set_transform_anchors(self, xforms, anchors):
        for t, a in zip(xforms, anchors):
            t.x_anchor, t.y_anchor = a

    def get_target_anchors(self):
        self._validate_cached_anchors()
        return self._target_anchors

    def _validate_cached_anchors(self):
        if self._target_anchors is None:
            anchors = self._get_all_anchors()
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

        sb_canvas_t = time.process_time()
        self._sb_canvas.update(dt)
        self._update_sb_canvas_accumulator += time.process_time() - sb_canvas_t

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
            average_sb_canvas_time = \
                self._update_sb_canvas_accumulator / \
                self._update_number_accumulator
            print(f'Average update times (seconds):')
            print(f'{"anchors":<20s} {average_anchor_time:<0.6f}')
            print(f'{"transforms":<20s} {average_xform_time:<0.6f}')
            print(f'{"sb canvas":<20s} {average_sb_canvas_time:<0.6f}')
            print(f'{"all":<20s} {average_update_time:<0.6f}')
            self._update_anchors_accumulator = 0
            self._update_transforms_accumulator = 0
            self._update_sb_canvas_accumulator = 0
            self._update_time_accumulator = 0
            self._update_number_accumulator = 0
