from distutils.version import StrictVersion

__all__ = ['main', 'log', 'export']

__version__ = '8.1.0'
# PEP396

strict_version = StrictVersion(__version__)
