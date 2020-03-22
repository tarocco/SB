from kivy.uix.floatlayout import FloatLayout
from kivy.properties import ReferenceListProperty, \
    BoundedNumericProperty
from kivy.graphics import ScissorPush, ScissorPop

from sb.sbscatter import SBScatter

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