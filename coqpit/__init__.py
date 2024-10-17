import importlib.metadata
from dataclasses import dataclass

from coqpit.coqpit import MISSING, Coqpit, check_argument

__all__ = ["dataclass", "MISSING", "Coqpit", "check_argument"]

__version__ = importlib.metadata.version("coqpit")
