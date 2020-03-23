from sb.component cimport Component

cdef class TransformBase(Component):
    cdef public object _parent
    cdef public list _children
    cdef public list _descendants
    cdef public int[:] _descendant_hierarchy