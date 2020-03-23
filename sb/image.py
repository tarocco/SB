from kivy.graphics.vertex_instructions import Rectangle
from sb.drawable import Drawable


class Image(Drawable):
    def __init__(self, _object, *args, **kwargs):
        super(Image, self).__init__(_object)
        self.texture = kwargs.get('texture', None)
        self.rectangle = Rectangle()
        #self._active_canvases = set()

    def _add_to_canvas(self, canvas):
        canvas.add(self.rectangle)

    def _remove_from_canvas(self, canvas):
        canvas.remove(self.rectangle)

    def update(self, dt):
        self.rectangle.texture = self.texture
        self.rectangle.pos = (self.transform.x, self.transform.y)
        size = (self.transform.width, self.transform.height)
        self.rectangle.size = size
