from setuptools.extension import Extension
from Cython.Build import cythonize
import numpy

mkidbin_extension = Extension(
    name="mkidcore.binfile.mkidbin",
    sources=["mkidcore/binfile/mkidbin.pyx", "mkidcore/binfile/binprocessor.c"],
    library_dirs=["mkidcore/binfile"],  # Location of .o file
    include_dirs=["mkidcore/binfile", numpy.get_include()],  # Location of the .h file
    extra_compile_args=["-std=gnu99", "-O3", '-pthread']
)


def pdm_build_update_setup_kwargs(ctx, kwargs):
    kwargs["ext_modules"] = cythonize([mkidbin_extension])
    return kwargs
