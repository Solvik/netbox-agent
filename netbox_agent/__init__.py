from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _get_version

try:
    __version__ = _get_version(__name__)
except PackageNotFoundError:
    pass
