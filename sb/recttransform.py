from sb.component import Component


def x_prop_setter(f):
    def wrapper(self, value):
        f(self, value)
        self._clear_x()

    return wrapper


def y_prop_setter(f):
    def wrapper(self, value):
        f(self, value)
        self._clear_y()

    return wrapper


class RectTransform(Component):
    def __init__(self, _object, *args, **kwargs):
        self._object = _object
        self._transform = self
        self._x_delta = kwargs.get('x_delta', 0)
        self._y_delta = kwargs.get('y_delta', 0)
        self._width = kwargs.get('width', 100)
        self._height = kwargs.get('height', 100)
        self._x_anchor = kwargs.get('x_anchor', 0.0)
        self._y_anchor = kwargs.get('y_anchor', 0.0)
        self._x_pivot = kwargs.get('x_pivot', 0.5)
        self._y_pivot = kwargs.get('y_pivot', 0.5)
        self._parent = None
        self._children = list()
        self._x = None
        self._y = None

    def _clear_x(self):
        self._x = None
        for child in self._children:
            child._clear_x()

    def _clear_y(self):
        self._y = None
        for child in self._children:
            child._clear_y()

    def _clear_xy(self):
        self._x = None
        self._y = None
        for child in self._children:
            child._clear_xy()

    def path(self):
        transform = self
        while transform is not None:
            yield transform
            transform = transform.parent

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, value):
        assert(isinstance(value, RectTransform))
        assert(value != self)
        if value is not self._parent:
            if self._parent is not None:
                self.parent._children.remove(self)
            if value is not None:
                if self in value.path():  # If value is a descendant of self
                    if value.parent is not None:
                        value.parent._children.remove(value)
                    value._parent = self.parent
                    if self.parent is not None:
                        self.parent._children.add(value)
                    value._children.append(self)
                    value._clear_xy()
                else:
                    value._children.append(self)
                    self._clear_xy()
            self._parent = value

    @property
    def children(self):
        return [child for child in self._children]

    @property
    def x_delta(self): return self._x_delta

    @x_delta.setter
    @x_prop_setter
    def x_delta(self, value):
        self._x_delta = value

    @property
    def y_delta(self): return self._y_delta

    @y_delta.setter
    @y_prop_setter
    def y_delta(self, value):
        self._y_delta = value

    @property
    def width(self): return self._width

    @width.setter
    @x_prop_setter
    def width(self, value):
        self._width = value

    @property
    def height(self): return self._height

    @height.setter
    @y_prop_setter
    def height(self, value):
        self._height = value

    @property
    def x_anchor(self): return self._x_anchor

    @x_anchor.setter
    @x_prop_setter
    def x_anchor(self, value):
        self._x_anchor = value

    @property
    def y_anchor(self): return self._y_anchor

    @y_anchor.setter
    @y_prop_setter
    def y_anchor(self, value):
        self._y_anchor = value

    @property
    def x_pivot(self): return self._x_pivot

    @x_pivot.setter
    @x_prop_setter
    def x_pivot(self, value):
        self._x_pivot = value

    @property
    def y_pivot(self): return self._y_pivot

    @y_pivot.setter
    @y_prop_setter
    def y_pivot(self, value):
        self._y_pivot = value

    @property
    def _parent_x(self):
        return self.parent.x if self.parent is not None else 0

    @property
    def _parent_y(self):
        return self.parent.y if self.parent is not None else 0

    @property
    def _parent_width(self):
        return self.parent.width if self.parent is not None else 0

    @property
    def _parent_height(self):
        return self.parent.height if self.parent is not None else 0

    @property
    def x(self):
        if self._x is None:
            self._x = self._parent_x + self.x_anchor * self._parent_width + \
                      self.x_pivot * self.width + self.x_delta
        return self._x

    @property
    def y(self):
        if self._y is None:
            self._y = self._parent_y + self.y_anchor * self._parent_height + \
                      self.y_pivot * self.height + self.y_delta
        return self._y
