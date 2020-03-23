from cython.parallel import prange
from libc.stdlib cimport malloc, free
from sb.transform_base cimport TransformBase


cdef inline float calculate_dimension(
        float parent_p,
        float parent_s,
        float anchor,
        float pivot,
        float s,
        float delta) nogil:
    return parent_p + anchor * parent_s + pivot * s + delta


cdef struct RectTransformModel:
    float x_delta, y_delta, width, height, \
        x_anchor, y_anchor, x_pivot, y_pivot, x, y
    int x_is_set, y_is_set


cdef class RectTransform(TransformBase):
    cdef RectTransformModel _model
    def __init__(self, _object, *args, **kwargs):
        super(RectTransform, self).__init__(_object, *args, **kwargs)
        self._model.x_delta = kwargs.get('x_delta', 0)
        self._model.y_delta = kwargs.get('y_delta', 0)
        self._model.width = kwargs.get('width', 100)
        self._model.height = kwargs.get('height', 100)
        self._model.x_anchor = kwargs.get('x_anchor', 0.0)
        self._model.y_anchor = kwargs.get('y_anchor', 0.0)
        self._model.x_pivot = kwargs.get('x_pivot', 0.5)
        self._model.y_pivot = kwargs.get('y_pivot', 0.5)
        self._model.x = 0
        self._model.y = 0
        self._model.x_is_set = 0
        self._model.y_is_set = 0

    def _clear_x(self):
        self._model.x_is_set = 0
        for child in self._children:
            child._clear_x()

    def _clear_y(self):
        self._model.y_is_set = 0
        for child in self._children:
            child._clear_y()

    def _clear_xy(self):
        self._model.x_is_set = 0
        self._model.y_is_set = 0
        for child in self._children:
            child._clear_xy()

    def _clear_model(self):
        self._clear_xy()

    @property
    def x_delta(self): return self._model.x_delta

    @x_delta.setter
    def x_delta(self, value):
        self._model.x_delta = value
        self._clear_x()

    @property
    def y_delta(self): return self._model.y_delta

    @y_delta.setter
    def y_delta(self, value):
        self._model.y_delta = value
        self._clear_y()

    @property
    def width(self): return self._model.width

    @width.setter
    def width(self, value):
        self._model.width = value
        self._clear_x()

    @property
    def height(self): return self._model.height

    @height.setter
    def height(self, value):
        self._model.height = value
        self._clear_y()

    @property
    def x_anchor(self): return self._model.x_anchor

    @x_anchor.setter
    def x_anchor(self, value):
        self._model.x_anchor = value
        self._clear_x()

    @property
    def y_anchor(self): return self._model.y_anchor

    @y_anchor.setter
    def y_anchor(self, value):
        self._model.y_anchor = value
        self._clear_y()

    @property
    def x_pivot(self): return self._model.x_pivot

    @x_pivot.setter
    def x_pivot(self, value):
        self._model.x_pivot = value
        self._clear_x()

    @property
    def y_pivot(self): return self._model.y_pivot

    @y_pivot.setter
    def y_pivot(self, value):
        self._model.y_pivot = value
        self._clear_y()

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
        if not self._model.x_is_set:
            self._model.x = calculate_dimension(
                self._parent_x,
                self._parent_width,
                self._model.x_anchor,
                self._model.x_pivot,
                self._model.width,
                self._model.x_delta)
            self._model.x_is_set = 1
            return self._model.x
        else:
            return self._model.x

    @property
    def y(self):
        if not self._model.y_is_set:
            self._model.y = calculate_dimension(
                self._parent_y,
                self._parent_height,
                self._model.y_anchor,
                self._model.y_pivot,
                self._model.height,
                self._model.y_delta)
            self._model.y_is_set = 1
            return self._model.y
        else:
            return self._model.y


cdef inline RectTransformModel* get_transform_model_pointer(
        RectTransform transform):
    return &transform._model


cpdef void transform_model_calc(list transforms, int[:] lut):
    '''
    :param transforms: must be a preorder traversal
    '''

    cdef RectTransformModel** models
    cdef int n_models
    cdef RectTransformModel* model
    cdef RectTransformModel* parent
    cdef int parent_idx
    cdef int i

    n_models = len(transforms)
    models = <RectTransformModel**>malloc(
        n_models * sizeof(RectTransformModel*))

    for i in range(n_models):
        models[i] = get_transform_model_pointer(transforms[i])

    for i in prange(n_models, nogil=True):
        model = models[i]
        parent_idx = lut[i]
        if parent_idx >= 0:
            parent = models[parent_idx]
            model.x = calculate_dimension(
                parent.x,
                parent.width,
                model.x_anchor,
                model.x_pivot,
                model.width,
                model.x_delta)
            model.y = calculate_dimension(
                parent.y,
                parent.height,
                model.y_anchor,
                model.y_pivot,
                model.width,
                model.y_delta)
        else:
            model.x = calculate_dimension(
                0,
                0,
                model.x_anchor,
                model.x_pivot,
                model.width,
                model.x_delta)
            model.y = calculate_dimension(
                0,
                0,
                model.y_anchor,
                model.y_pivot,
                model.width,
                model.y_delta)
        model.x_is_set = 1
        model.y_is_set = 1
    free(models)
