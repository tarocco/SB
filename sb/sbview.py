from kivy.uix.floatlayout import FloatLayout
from kivy.properties import ReferenceListProperty, \
    BoundedNumericProperty
from kivy.graphics import ScissorPush, ScissorPop


class SBView(FloatLayout):
    def __init__(self, **kwargs):
        super(SBView, self).__init__(**kwargs)
        self.scatter = None  # on_kv_post
        self._prior_width = None
        self._prior_height = None

        self.bind(width=self.width_changed)
        self.bind(height=self.height_changed)

        # Set and forget
        with self.canvas.after:
            ScissorPop()

    def on_kv_post(self, base_widget):
        # Precondition
        self.scatter = self.children[0]

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
        else:
            self.scatter.width = value
        self._prior_width = value

    def height_changed(self, src, value):
        self._update_clipping_mask()
        if self._prior_height:
            difference = value - self._prior_height
            self.scatter.y += difference * self.pivot_y
        else:
            self.scatter.height = value
        self._prior_height = value

    pivot_x = BoundedNumericProperty(0.5, min=0.0, max=1.0, bind=['width'])
    pivot_y = BoundedNumericProperty(0.5, min=0.0, max=1.0, bind=['height'])
    pivot = ReferenceListProperty(pivot_x, pivot_y)
