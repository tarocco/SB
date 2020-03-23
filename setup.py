from setuptools import setup, Extension
from Cython.Build import cythonize

ext_options = {
    "compiler_directives": {
        "language_level": "3",
        "profile": True
    },
    "annotate": True
}

extensions = [
    Extension("sb.transform_base", sources=["sb/transform_base.pyx"]),
    Extension("sb.recttransform", sources=["sb/recttransform.pyx"]),
    Extension("sb.component", sources=["sb/component.pyx"]),
    "sb/sbobject.pyx",
    "sb/sbcanvas.pyx"
]

setup(
    ext_modules=cythonize(extensions, **ext_options)
)
