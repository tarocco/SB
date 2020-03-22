from kivy.graphics.vertex_instructions import Rectangle
from sb.drawable import Drawable


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
        self.rectangle.texture = self.texture
        self.rectangle.pos = (self.transform.x, self.transform.y)
        size = (self.transform.width, self.transform.height)
        self.rectangle.size = size
