import importlib.metadata

from coqpit.coqpit import MISSING, Coqpit, check_argument

__all__ = ["MISSING", "Coqpit", "check_argument"]

__version__ = importlib.metadata.version("coqpit-config")
