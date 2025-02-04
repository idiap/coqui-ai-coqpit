"""Simple, light-weight config handling through Python data classes."""

from __future__ import annotations

import argparse
import contextlib
import functools
import json
import operator
import typing
import warnings
from collections.abc import Callable, ItemsView, Iterable, Iterator, MutableMapping
from dataclasses import MISSING as _MISSING
from dataclasses import Field, asdict, dataclass, fields, is_dataclass, replace
from pathlib import Path
from pprint import pprint
from types import UnionType
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeAlias, TypeGuard, TypeVar, Union, overload

from typing_extensions import Self, TypeIs

if TYPE_CHECKING:  # pragma: no cover
    import os
    from dataclasses import _MISSING_TYPE

    from _typeshed import SupportsKeysAndGetItem

_T = TypeVar("_T")
MISSING: Any = "???"


class _NoDefault(Generic[_T]):
    pass


NoDefaultVar: TypeAlias = _NoDefault[_T] | _T
no_default: NoDefaultVar[Any] = _NoDefault()

FieldType: TypeAlias = Union[str, type, "UnionType"]


def _is_primitive_type(field_type: FieldType) -> TypeGuard[type]:
    """Check if the input type is one of `int, float, str, bool`.

    Args:
        field_type: input type to check.

    Returns:
        bool: True if input type is one of `int, float, str, bool`.
    """
    return field_type is int or field_type is float or field_type is str or field_type is bool


def _is_list(field_type: FieldType) -> TypeGuard[type]:
    """Check if the input type is `list`.

    Args:
        field_type: input type.

    Returns:
        bool: True if input type is `list`
    """
    return field_type is list or typing.get_origin(field_type) is list


def _parse_list_union(field_type: FieldType) -> type | None:
    """Check if the input type matches `_T | list[_T]`.

    Args:
        field_type: input type.

    Returns:
        bool: _T, if input type matches `_T | list[_T]`, else None
    """
    if not _is_union(field_type):
        return None

    def _get_base_type(field_type: type) -> type:
        return typing.get_args(field_type)[0] if _is_list(field_type) else field_type

    args = typing.get_args(field_type)
    is_list = [_is_list(arg) for arg in args]
    base_types = [_get_base_type(arg) for arg in args]
    return base_types[0] if len(args) == 2 and sum(is_list) == 1 and base_types[0] == base_types[1] else None  # noqa: PLR2004


def _is_dict(field_type: FieldType) -> TypeGuard[type]:
    """Check if the input type is `dict`.

    Args:
        field_type: input type.

    Returns:
        bool: True if input type is `dict`
    """
    return field_type is dict or typing.get_origin(field_type) is dict


def _is_union(field_type: FieldType) -> TypeIs[UnionType]:
    """Check if the input type is `Union`.

    Args:
        field_type: input type.

    Returns:
        bool: True if input type is `Union`
    """
    origin = typing.get_origin(field_type)
    return origin is Union or origin is UnionType


def _is_union_and_not_simple_optional(field_type: FieldType) -> TypeGuard[UnionType]:
    """Check if the input type is `Union`.

    Note: `int | None` would be of type Union, but here we don't consider such
    cases where the only other accepted type is None.

    Args:
        field_type: input type.

    Returns:
        bool: True if input type is `Union` and not optional type like `int | None`
    """
    args = typing.get_args(field_type)
    is_python_union = _is_union(field_type)
    if is_python_union and len(args) == 2 and type(None) in args:  # noqa: PLR2004
        # This is an Optional type like `int | None`
        return False
    return is_python_union


def _default_value(x: Field[_T]) -> _T | Literal[_MISSING_TYPE.MISSING]:
    """Return the default value of the input Field.

    Args:
        x (Field): input Field.

    Returns:
        object: default value of the input Field.
    """
    if x.default != MISSING and x.default is not _MISSING:
        return x.default
    if x.default_factory != MISSING and x.default_factory is not _MISSING:
        return x.default_factory()
    return x.default


def _is_optional_field(field_type: FieldType) -> TypeGuard[UnionType]:
    """Check if the input field type is optional.

    Args:
        field_type: input Field's type to check.

    Returns:
        bool: True if the input field type is optional.
    """
    return type(None) in typing.get_args(field_type)


def _drop_none_type(field_type: FieldType) -> FieldType:
    """Drop None from Union-like types.

    >>> _drop_none_type(str | int | None)
    str | int
    """
    if not _is_union(field_type):
        return field_type
    args = list(typing.get_args(field_type))
    if type(None) in args:
        args.remove(type(None))
    if len(args) == 1:
        return typing.cast(type, args[0])
    return typing.cast(UnionType, functools.reduce(lambda a, b: a | b, args))


def _serialize(x: Any) -> Any:
    """Pick the right serialization for the datatype of the given input.

    Args:
        x (object): input object.

    Returns:
        object: serialized object.
    """
    if isinstance(x, Path):
        return str(x)
    if isinstance(x, dict):
        return {k: _serialize(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_serialize(xi) for xi in x]
    if isinstance(x, Serializable) or issubclass(type(x), Serializable):
        return x.serialize()
    if isinstance(x, type) and issubclass(x, Serializable):
        return x.serialize(x())
    return x


def _deserialize_dict(x: dict[Any, Any]) -> dict[Any, Any]:
    """Deserialize dict.

    Args:
        x (Dict): value to deserialized.

    Returns:
        Dict: deserialized dictionary.
    """
    if not isinstance(x, dict):
        msg = f"Value `{x}` is not a dictionary"
        raise TypeError(msg)
    out_dict: dict[Any, Any] = {}
    for k, v in x.items():
        if v is None:  # if {'key':None}
            out_dict[k] = None
        else:
            out_dict[k] = _deserialize(v, type(v))
    return out_dict


def _deserialize_list(x: list[Any], field_type: FieldType) -> list[Any]:
    """Deserialize values for List typed fields.

    Args:
        x (List): value to be deserialized
        field_type (Type): field type.

    Raises:
        ValueError: Coqpit does not support multi type-hinted lists.

    Returns:
        [List]: deserialized list.
    """
    if not isinstance(x, list):
        msg = f"Value `{x}` does not match field type `{field_type}`"
        raise TypeError(msg)
    field_args = typing.get_args(field_type)
    if len(field_args) == 0:
        return x
    if len(field_args) > 1:
        msg = "Coqpit does not support multi-type hinted 'List'"
        raise ValueError(msg)
    field_arg = field_args[0]
    # if field type is TypeVar set the current type by the value's type.
    if isinstance(field_arg, TypeVar):
        field_arg = type(x)
    return [_deserialize(xi, field_arg) for xi in x]


def _deserialize_union(x: Any, field_type: UnionType) -> Any:
    """Deserialize values for Union typed fields.

    Args:
        x (Any): value to be deserialized.
        field_type (Type): field type.

    Returns:
        [Any]: deserialized value.
    """
    for arg in typing.get_args(field_type):
        # stop after first matching type in Union
        try:
            x = _deserialize(x, arg)
            break
        except (TypeError, ValueError):
            pass
    return x


def _deserialize_primitive_types(
    x: int | float | str | bool | None,  # noqa: PYI041
    field_type: FieldType,
) -> int | float | str | bool | None:
    """Deserialize python primitive types (float, int, str, bool).

    It handles `inf` values exclusively and keeps them float against int fields since int does not support inf values.

    Args:
        x (Union[int, float, str, bool]): value to be deserialized.
        field_type (Type): field type.

    Returns:
        Union[int, float, str, bool]: deserialized value.
    """
    base_type = _drop_none_type(field_type)
    if base_type is not float and base_type is not int and base_type is not str and base_type is not bool:
        raise TypeError
    base_type = typing.cast(type[int | float | str | bool], base_type)

    type_mismatch = f"Value `{x}` does not match field type `{field_type}`"
    if x is None and type(None) in typing.get_args(field_type):
        return None
    if isinstance(x, str):
        if base_type is not str:
            raise TypeError(type_mismatch)
        return x
    if isinstance(x, bool):
        if base_type is not bool:
            raise TypeError(type_mismatch)
        return x
    if isinstance(x, int | float):
        if x == float("inf") or x == float("-inf"):
            # if value type is inf return regardless.
            return x
        if base_type is not int and base_type is not float:
            raise TypeError(type_mismatch)
        return base_type(x)
    raise TypeError(type_mismatch)


def _deserialize_path(x: Any, field_type: FieldType) -> Path | None:
    """Deserialize to a Path."""
    if x is None and _is_optional_field(field_type):
        return None
    return Path(x)


def _deserialize(x: Any, field_type: FieldType) -> Any:
    """Pick the right deserialization for the given object and the corresponding field type.

    Args:
        x (object): object to be deserialized.
        field_type (type): expected type after deserialization.

    Returns:
        object: deserialized object

    """
    if isinstance(field_type, str):
        msg = "Strings as type hints are not supported."
        raise NotImplementedError(msg)
    if _is_dict(_drop_none_type(field_type)):
        return _deserialize_dict(x)
    if _is_list(_drop_none_type(field_type)):
        return _deserialize_list(x, _drop_none_type(field_type))
    if _is_union_and_not_simple_optional(field_type):
        return _deserialize_union(x, field_type)
    if not _is_union(field_type) and isinstance(field_type, type) and issubclass(field_type, Serializable):
        return field_type.deserialize_immutable(x)
    if _drop_none_type(field_type) is Path:
        return _deserialize_path(x, field_type)
    if _is_primitive_type(_drop_none_type(field_type)):
        return _deserialize_primitive_types(x, field_type)
    msg = f"Type '{type(x)}' of value '{x}' does not match declared '{field_type}' field type."
    raise TypeError(msg)


CoqpitType: TypeAlias = MutableMapping[str, "CoqpitNestedValue"]
CoqpitNestedValue: TypeAlias = Union["CoqpitValue", CoqpitType]
CoqpitValue: TypeAlias = str | int | float | bool | None


# TODO: It should be possible to get rid of the next 3 `type: ignore`. At
# nested levels, the key can be `str | int` as well, not just `str`.
def _rsetattr(obj: CoqpitType, keys: str, val: CoqpitValue) -> None:
    """Recursive setattr (supports dotted key names)."""
    pre, _, post = keys.rpartition(".")
    target = _rgetattr(obj, pre) if pre else obj
    if post.isnumeric():
        operator.setitem(target, int(post), val)  # type: ignore[misc]
    else:
        setattr(target, post, val)


def _rgetattr(obj: CoqpitType, keys: str) -> CoqpitType:
    """Recursive getattr (supports dotted key names)."""
    v = obj
    for k in keys.split("."):
        v = operator.getitem(v, int(k)) if k.isnumeric() else getattr(v, k)  # type: ignore[arg-type]
    return v


def _rsetitem(obj: CoqpitType, keys: str, value: CoqpitValue) -> None:
    """Recursive setitem (supports dotted key names).

    _rsetitem(a, "b.c", 1) => a["b"]["c"] = 1
    """
    pre, _, post = keys.rpartition(".")
    operator.setitem(_rgetitem(obj, pre) if pre else obj, post, value)


def _rgetitem(obj: CoqpitType, keys: str) -> CoqpitType:
    """Recursive getitem (supports dotted key names).

    _rgetitem(a, "b.c") => a["b"]["c"]
    """
    v = obj
    for k in keys.split("."):
        v = operator.getitem(v, int(k) if k.isnumeric() else k)  # type: ignore[arg-type]
    return v


@dataclass
class Serializable:
    """Gives serialization ability to any inheriting dataclass."""

    def __post_init__(self) -> None:
        """Validate contracts and check required arguments are specified."""
        self._validate_contracts()
        for key, value in self.__dict__.items():
            if value is no_default:
                msg = f"__init__ missing 1 required argument: '{key}'"
                raise TypeError(msg)

    def _validate_contracts(self) -> None:
        """Validate contracts specified in the dataclass."""
        dataclass_fields = fields(self)

        for field in dataclass_fields:
            value = getattr(self, field.name)

            if value is None and not _is_optional_field(field.type):
                msg = f"{field.name} is not optional"
                raise TypeError(msg)

            contract = field.metadata.get("contract", None)

            if contract is not None and value is not None and not contract(value):
                msg = f"break the contract for {field.name}, {self.__class__.__name__}"
                raise ValueError(msg)

    def validate(self) -> None:
        """Validate if object can serialize / deserialize correctly."""
        self._validate_contracts()
        if self != self.__class__().deserialize(json.loads(json.dumps(self.serialize()))):
            msg = "could not be deserialized with same value"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, Any]:
        """Transform serializable object to dict."""
        cls_fields = fields(self)
        o = {}
        for cls_field in cls_fields:
            o[cls_field.name] = getattr(self, cls_field.name)
        return o

    def serialize(self) -> dict[str, Any]:
        """Serialize object to be json serializable representation."""
        if not is_dataclass(self):
            msg = "need to be decorated as dataclass"
            raise TypeError(msg)

        dataclass_fields = fields(self)

        o = {}

        for field in dataclass_fields:
            value = getattr(self, field.name)
            value = _serialize(value)
            o[field.name] = value
        return o

    def deserialize(self, data: dict[str, Any]) -> Self:
        """Parse input dictionary and deserialize its fields to a dataclass.

        Returns:
            self: deserialized `self`.
        """
        if not isinstance(data, dict):
            raise TypeError
        data = data.copy()
        init_kwargs = {}
        for field in fields(self):
            # if field.name == 'dataset_config':
            if field.name not in data:
                if field.name in vars(self):
                    init_kwargs[field.name] = vars(self)[field.name]
                    continue
                msg = f' [!] Missing required field "{field.name}"'
                raise ValueError(msg)
            value = data.get(field.name, _default_value(field))
            if value is None:
                init_kwargs[field.name] = value
                continue
            if value == MISSING:
                msg = f"deserialized with unknown value for {field.name} in {self.__class__.__name__}"
                raise ValueError(msg)
            try:
                value = _deserialize(value, field.type)
            except TypeError:
                warnings.warn(
                    (
                        f"Type mismatch in {type(self).__name__}\n"
                        f"Failed to deserialize field: {field.name} ({field.type}) = {value}\n"
                        f"Replaced it with field's default value: {_default_value(field)}"
                    ),
                    stacklevel=2,
                )
                value = _default_value(field)
            init_kwargs[field.name] = value
        for k, v in init_kwargs.items():
            setattr(self, k, v)
        return self

    @classmethod
    def deserialize_immutable(cls, data: dict[str, Any]) -> Self:
        """Parse input dictionary and deserialize its fields to a dataclass.

        Returns:
            Newly created deserialized object.
        """
        if not isinstance(data, dict):
            raise TypeError
        data = data.copy()
        init_kwargs = {}
        for field in fields(cls):
            # if field.name == 'dataset_config':
            if field.name not in data:
                if field.name in vars(cls):
                    init_kwargs[field.name] = vars(cls)[field.name]
                    continue
                # if not in cls and the default value is not Missing use it
                default_value = _default_value(field)
                if default_value not in (MISSING, _MISSING):
                    init_kwargs[field.name] = default_value
                    continue
                msg = f' [!] Missing required field "{field.name}"'
                raise ValueError(msg)
            value = data.get(field.name, _default_value(field))
            if value is None:
                init_kwargs[field.name] = value
                continue
            if value == MISSING:
                msg = f"Deserialized with unknown value for {field.name} in {cls.__name__}"
                raise ValueError(msg)
            value = _deserialize(value, field.type)
            init_kwargs[field.name] = value
        return cls(**init_kwargs)


# ---------------------------------------------------------------------------- #
#                        Argument Parsing from `argparse`                      #
# ---------------------------------------------------------------------------- #


def _get_help(field: Field[Any]) -> str:
    try:
        return str(field.metadata["help"])
    except KeyError:
        return ""


def _add_argument(  # noqa: C901, PLR0913, PLR0912, PLR0915
    parser: argparse.ArgumentParser,
    field_name: str,
    field_type: FieldType,
    field_default: Any,
    field_default_factory: Callable[[], Any] | Literal[_MISSING_TYPE.MISSING],
    field_help: str,
    arg_prefix: str = "",
    help_prefix: str = "",
    *,
    relaxed_parser: bool = False,
) -> argparse.ArgumentParser:
    """Add a new argument to the argparse parser, matching the given field."""
    if isinstance(field_type, str):
        msg = "Strings as type hints are not supported."
        raise NotImplementedError(msg)
    default = None
    has_default = False
    if field_default:
        has_default = True
        default = field_default
    elif field_default_factory is not None and field_default_factory is not _MISSING:
        has_default = True
        default = field_default_factory()

    if (
        not has_default
        and not _is_primitive_type(_drop_none_type(field_type))
        and not _is_list(_drop_none_type(field_type))
        and _parse_list_union(_drop_none_type(field_type)) is None
    ):
        # aggregate types (fields with a Coqpit subclass as type) are not
        # supported without None
        return parser
    arg_prefix = field_name if arg_prefix == "" else f"{arg_prefix}.{field_name}"
    help_prefix = field_help if help_prefix == "" else f"{help_prefix} - {field_help}"
    if _is_dict(field_type):
        # NOTE: accept any string in json format as input to dict field.
        parser.add_argument(
            f"--{arg_prefix}",
            dest=arg_prefix,
            default=json.dumps(field_default) if field_default else None,
            type=json.loads,
        )
    elif _is_list(_drop_none_type(field_type)):
        field_args = typing.get_args(_drop_none_type(field_type))
        if len(field_args) > 1 and not relaxed_parser:
            msg = "Coqpit does not support multi-type hinted 'List'"
            raise ValueError(msg)
        if len(field_args) == 0:
            msg = "Coqpit does not support un-hinted 'List'"
            raise ValueError(msg)
        list_field_type = field_args[0]

        # TODO: handle list of lists
        if _is_list(list_field_type) and relaxed_parser:
            return parser

        if not has_default or field_default_factory is list:
            if not _is_primitive_type(list_field_type) and not relaxed_parser:
                msg = " [!] Empty list with non primitive inner type is currently not supported."
                raise NotImplementedError(msg)

            # If the list's default value is None, the user can specify the entire list by passing multiple parameters
            parser.add_argument(
                f"--{arg_prefix}",
                nargs="*",
                type=list_field_type,
                help=f"Coqpit Field: {help_prefix}",
            )
        else:
            # If a default value is defined, just enable editing the values from argparse
            # TODO: allow inserting a new value/obj to the end of the list.
            if not isinstance(default, list):
                msg = f"Default value must be a list, got {default}"
                raise TypeError(msg)
            for idx, fv in enumerate(default):
                parser = _add_argument(
                    parser,
                    str(idx),
                    list_field_type,
                    fv,
                    field_default_factory,
                    field_help="",
                    help_prefix=f"{help_prefix} (item {idx})",
                    arg_prefix=f"{arg_prefix}",
                    relaxed_parser=relaxed_parser,
                )
    # Fields matching: _T | list[_T] ( | None)
    elif (list_field_type := _parse_list_union(_drop_none_type(field_type))) is not None:
        if not has_default or field_default_factory is list:
            if not _is_primitive_type(list_field_type) and not relaxed_parser:
                msg = " [!] Empty list with non primitive inner type is currently not supported."
                raise NotImplementedError(msg)

            # If the list's default value is None, the user can specify the entire list by passing multiple parameters
            parser.add_argument(
                f"--{arg_prefix}",
                nargs="*",
                type=list_field_type,
                help=f"Coqpit Field: {help_prefix}",
            )
        # If a default value is defined, just enable editing the values from argparse
        # TODO: allow inserting a new value/obj to the end of the list.
        elif not isinstance(default, list):
            parser.add_argument(
                f"--{arg_prefix}",
                default=default,
                type=list_field_type,
                help=f"Coqpit Field: {help_prefix}",
            )
        else:
            for idx, fv in enumerate(default):
                parser = _add_argument(
                    parser,
                    str(idx),
                    list_field_type,
                    fv,
                    field_default_factory,
                    field_help="",
                    help_prefix=f"{help_prefix} (item {idx})",
                    arg_prefix=f"{arg_prefix}",
                    relaxed_parser=relaxed_parser,
                )
    elif _is_union_and_not_simple_optional(field_type):
        # TODO: currently I don't know how to handle Union type on argparse
        if not relaxed_parser:
            msg = " [!] Parsing `Union` field from argparse is not yet implemented. Please create an issue."
            raise NotImplementedError(msg)
    elif not _is_union(field_type) and issubclass(field_type, Coqpit):
        if not isinstance(default, Coqpit):
            msg = f"Default value must be a Coqpit instance, got {default}"
            raise TypeError(msg)
        return default.init_argparse(
            instance=default,
            parser=parser,
            arg_prefix=arg_prefix,
            help_prefix=help_prefix,
            relaxed_parser=relaxed_parser,
        )
    elif field_type is bool:

        def parse_bool(x: str) -> bool:
            if x not in ("true", "false"):
                msg = f' [!] Value for boolean field must be either "true" or "false". Got "{x}".'
                raise ValueError(msg)
            return x == "true"

        parser.add_argument(
            f"--{arg_prefix}",
            type=parse_bool,
            default=field_default,
            help=f"Coqpit Field: {help_prefix}",
            metavar="true/false",
        )
    elif _is_primitive_type(_drop_none_type(field_type)):
        base_type = _drop_none_type(field_type)
        if _is_union(base_type):
            raise TypeError
        parser.add_argument(
            f"--{arg_prefix}",
            default=field_default,
            type=base_type,
            help=f"Coqpit Field: {help_prefix}",
        )
    elif not relaxed_parser:
        msg = f" [!] '{field_type}' is not supported by arg_parser. Please file a bug report."
        raise NotImplementedError(msg)
    return parser


# ---------------------------------------------------------------------------- #
#                               Main Coqpit Class                              #
# ---------------------------------------------------------------------------- #


@dataclass
class Coqpit(Serializable, CoqpitType):
    """Coqpit base class to be inherited by any Coqpit dataclasses.

    It overrides Python `dict` interface and provides `dict` compatible API.
    It also enables serializing/deserializing a dataclass to/from a json file,
    plus some semi-dynamic type and value check.

    Note that it does not support all datatypes and likely to fail in some cases.
    """

    _initialized = False

    def _is_initialized(self) -> bool:
        """Check if Coqpit is initialized.

        Useful to prevent running some aux functions
        at the initialization when no attribute has been defined.
        """
        return "_initialized" in vars(self) and self._initialized

    def __post_init__(self) -> None:
        """Check values if a check_values() method is defined."""
        self._initialized = True
        with contextlib.suppress(AttributeError):
            self.check_values()

    ## `dict` API functions

    def __iter__(self) -> Iterator[str]:
        """Return iterator over the Coqpit."""
        return iter(asdict(self))

    def __len__(self) -> int:
        """Return the number of fields in the Coqpit."""
        return len(fields(self))

    def __setitem__(self, arg: str, value: Any) -> None:
        """Set the value for the given attribute."""
        setattr(self, arg, value)

    def __getitem__(self, arg: str) -> Any:
        """Access class attributes with ``[arg]``."""
        return self.__dict__[arg]

    def __delitem__(self, arg: str) -> None:
        """Remove an attribute."""
        delattr(self, arg)

    def _keytransform(self, key: str) -> str:
        return key

    ## end `dict` API functions

    def __getattribute__(self, arg: str) -> Any:
        """Check if the mandatory field is defined when accessing it."""
        value = super().__getattribute__(arg)
        if isinstance(value, str) and value == "???":
            msg = f" [!] MISSING field {arg} must be defined."
            raise AttributeError(msg)
        return value

    def __contains__(self, arg: object) -> bool:
        """Check whether the Coqpit contains the given attribute."""
        return arg in self.to_dict()

    def get(self, key: str, default: Any = None) -> Any:
        """Return value of the given attribute if present, otherwise the default."""
        if self.has(key):
            return asdict(self)[key]
        return default

    def items(self) -> ItemsView[str, Any]:
        """Return (key, value) items of the Coqpit."""
        return asdict(self).items()

    def merge(self, coqpits: Coqpit | list[Coqpit]) -> None:
        """Merge a coqpit instance or a list of coqpit instances to self.

        Note that it does not pass the fields and overrides attributes with
        the last Coqpit instance in the given List.
        TODO: find a way to merge instances with all the class internals.

        Args:
            coqpits (Union[Coqpit, List[Coqpit]]): coqpit instance or list of instances to be merged.
        """

        def _merge(coqpit: Coqpit) -> None:
            self.__dict__.update(coqpit.__dict__)
            self.__annotations__.update(coqpit.__annotations__)
            self.__dataclass_fields__.update(coqpit.__dataclass_fields__)

        if isinstance(coqpits, list):
            for coqpit in coqpits:
                _merge(coqpit)
        else:
            _merge(coqpits)

    def check_values(self) -> None:
        """Perform data validation after initialization.

        Can be implemented in subclasses.
        """

    def has(self, arg: str) -> bool:
        """Check whether the Coqpit has the given attribute."""
        return arg in vars(self)

    def copy(self) -> Self:
        """Return a copy of the Coqpit."""
        return replace(self)

    @overload
    def update(self, other: SupportsKeysAndGetItem[str, CoqpitNestedValue], /, **kwargs: CoqpitNestedValue) -> None: ...
    @overload
    def update(self, other: Iterable[tuple[str, CoqpitNestedValue]], /, **kwargs: CoqpitNestedValue) -> None: ...
    @overload
    def update(self, /, **kwargs: CoqpitNestedValue) -> None: ...
    def update(self, other: Any = (), /, **kwargs: CoqpitNestedValue) -> None:
        """Update Coqpit fields by the input ```dict```.

        Args:
            other: dictionary or iterable with new values.
            **kwargs: alternative way to pass new keys and values.
        """
        if isinstance(other, dict):
            for key in other:
                setattr(self, key, other[key])
        elif hasattr(other, "keys"):
            for key in other.keys():  # noqa: SIM118
                setattr(self, key, other[key])
        else:
            for key, value in other:
                setattr(self, key, value)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def pprint(self) -> None:
        """Print Coqpit fields in a format."""
        pprint(asdict(self))  # noqa: T203

    def to_dict(self) -> dict[str, Any]:
        """Convert the Coqpit to a dictionary, serializing any values."""
        return self.serialize()

    def from_dict(self, data: dict[str, Any]) -> None:
        """Update Coqpit from the dictionary."""
        self.deserialize(data)

    @classmethod
    def new_from_dict(cls, data: dict[str, Any]) -> Self:
        """Create a new Coqpit from a dictionary."""
        return cls.deserialize_immutable(data)

    def to_json(self) -> str:
        """Return a JSON string representation."""
        return json.dumps(self.to_dict(), indent=4)

    def save_json(self, file_name: str | os.PathLike[Any]) -> None:
        """Save Coqpit to a json file.

        Args:
            file_name (str): path to the output json file.
        """
        with Path(file_name).open("w", encoding="utf8") as f:
            json.dump(self.to_dict(), f, indent=4)

    def load_json(self, file_name: str | os.PathLike[Any]) -> None:
        """Load a json file and update matching config fields with type checking.

        Non-matching parameters in the json file are ignored.

        Args:
            file_name (str): path to the json file.

        Returns:
            Coqpit: new Coqpit with updated config fields.
        """
        with Path(file_name).open(encoding="utf8") as f:
            input_str = f.read()
            dump_dict = json.loads(input_str)
        self.deserialize(dump_dict)
        self.check_values()

    @classmethod
    def init_from_argparse(
        cls,
        args: argparse.Namespace | list[str] | None = None,
        arg_prefix: str = "coqpit",
    ) -> Self:
        """Create a new Coqpit instance from argparse input.

        Args:
            args (namespace or list of str, optional): parsed argparse.Namespace
              or list of command line parameters. If unspecified will use a
              newly created parser with ```init_argparse()```.
            arg_prefix: prefix to add to CLI parameters. Gets forwarded to
              ```init_argparse``` when ```args``` is not passed.
        """
        if not args:
            # If args was not specified, parse from sys.argv
            parser = cls.init_argparse(arg_prefix=arg_prefix)
            args = parser.parse_args()
        if isinstance(args, list):
            # If a list was passed in (eg. the second result of
            # `parse_known_args`, run that through argparse first to get a
            # parsed Namespace
            parser = cls.init_argparse(arg_prefix=arg_prefix)
            args = parser.parse_args(args)

        # Handle list and object attributes with defaults, which can be modified
        # directly (eg. --coqpit.list.0.val_a 1), by constructing real objects
        # from defaults and passing those to `cls.__init__`
        args_with_lists_processed: CoqpitType = {}
        class_fields = fields(cls)
        for field in class_fields:
            has_default = False
            default = None
            field_default = field.default if field.default is not _MISSING else None
            field_default_factory = field.default_factory if field.default_factory is not _MISSING else None
            if field_default:
                has_default = True
                default = field_default
            elif field_default_factory:
                has_default = True
                default = field_default_factory()

            if has_default and (not _is_primitive_type(field.type) or _is_list(field.type)):
                args_with_lists_processed[field.name] = default

        args_dict = vars(args)
        for key, v in args_dict.items():
            # Remove argparse prefix (eg. "--coqpit." if present)
            k = key.removeprefix(f"{arg_prefix}.")
            _rsetitem(args_with_lists_processed, k, v)

        return cls(**args_with_lists_processed)

    def parse_args(
        self,
        args: argparse.Namespace | list[str] | None = None,
        arg_prefix: str = "coqpit",
    ) -> None:
        """Update config values from argparse arguments with some meta-programming ✨.

        Args:
            args (namespace or list of str, optional): parsed argparse.Namespace
              or list of command line parameters. If unspecified will use a
              newly created parser with ```init_argparse()```.
            arg_prefix: prefix to add to CLI parameters. Gets forwarded to
              ```init_argparse``` when ```args``` is not passed.
        """
        if not args:
            # If args was not specified, parse from sys.argv
            parser = self.init_argparse(instance=self, arg_prefix=arg_prefix)
            args = parser.parse_args()
        if isinstance(args, list):
            # If a list was passed in (eg. the second result of
            # `parse_known_args`, run that through argparse first
            # to get a parsed Namespace
            parser = self.init_argparse(instance=self, arg_prefix=arg_prefix)
            args = parser.parse_args(args)

        args_dict = vars(args)

        for key, v in args_dict.items():
            k = key.removeprefix(f"{arg_prefix}.")
            try:
                _rgetattr(self, k)
            except (TypeError, AttributeError) as e:
                msg = f" [!] '{k}' not exist to override from argparse."
                raise TypeError(msg) from e

            _rsetattr(self, k, v)

        self.check_values()

    def parse_known_args(
        self,
        args: argparse.Namespace | list[str] | None = None,
        arg_prefix: str = "coqpit",
        *,
        relaxed_parser: bool = False,
    ) -> list[str]:
        """Update config values from argparse arguments. Ignore unknown arguments.

           This is analog to argparse.ArgumentParser.parse_known_args (vs parse_args).

        Args:
            args (namespace or list of str, optional): parsed argparse.Namespace
              or list of command line parameters. If unspecified will use a
              newly created parser with ```init_argparse()```.
            arg_prefix: prefix to add to CLI parameters. Gets forwarded to
              ```init_argparse``` when ```args``` is not passed.
            relaxed_parser (bool, optional): If True, do not force all the fields
              to have compatible types with the argparser. Defaults to False.

        Returns:
            List of unknown parameters.
        """
        unknown: list[str] = []
        if not args:
            # If args was not specified, parse from sys.argv
            parser = self.init_argparse(instance=self, arg_prefix=arg_prefix, relaxed_parser=relaxed_parser)
            args, unknown = parser.parse_known_args()
        if isinstance(args, list):
            # If a list was passed in (eg. the second result of
            # `parse_known_args`, run that through argparse first to get a
            # parsed Namespace
            parser = self.init_argparse(instance=self, arg_prefix=arg_prefix, relaxed_parser=relaxed_parser)
            args, unknown = parser.parse_known_args(args)

        self.parse_args(args, arg_prefix=arg_prefix)
        return unknown

    @classmethod
    def init_argparse(
        cls,
        *,
        instance: Self | None = None,
        parser: argparse.ArgumentParser | None = None,
        arg_prefix: str = "coqpit",
        help_prefix: str = "",
        relaxed_parser: bool = False,
    ) -> argparse.ArgumentParser:
        """Create an argparse parser that can parse the Coqpit fields.

        This allows to edit values through command-line.

        Args:
            instance (Coqpit, optional): instance of the given Coqpit class
                                         to initialize any default values.
            parser (argparse.ArgumentParser, optional): argparse.ArgumentParser
              instance. If unspecified a new one will be created.
            arg_prefix (str, optional): Prefix to be used for the argument name.
              Defaults to 'coqpit'.
            help_prefix (str, optional): Prefix to be used for the argument
              description. Defaults to ''.
            relaxed_parser (bool, optional): If True, do not force all the fields
              to have compatible types with the argparser. Defaults to False.

        Returns:
            argparse.ArgumentParser: parser instance with the new arguments.
        """
        if not parser:
            parser = argparse.ArgumentParser()
        cls_or_instance = cls if instance is None else instance
        class_fields = fields(cls_or_instance)
        for field in class_fields:
            # use the current value of the field to prevent dropping the current value,
            # else use the default value of the field
            field_default = vars(cls_or_instance).get(
                field.name,
                field.default if field.default is not _MISSING else None,
            )
            field_type = field.type
            field_default_factory = field.default_factory
            field_help = _get_help(field)
            _add_argument(
                parser,
                field.name,
                field_type,
                field_default,
                field_default_factory,
                field_help,
                arg_prefix,
                help_prefix,
                relaxed_parser=relaxed_parser,
            )
        return parser


def check_argument(  # noqa: C901, PLR0913
    name: str,
    c: dict[str, Any],
    *,
    is_path: bool = False,
    prerequest: list[str] | str | None = None,
    enum_list: list[Any] | None = None,
    max_val: float | None = None,
    min_val: float | None = None,
    restricted: bool = False,
    alternative: str | None = None,
    allow_none: bool = True,
) -> None:
    """Simple type and value checking for Coqpit.

    It is intended to be used under ```__post_init__()``` of config dataclasses.

    Args:
        name (str): name of the field to be checked.
        c (dict): config dictionary.
        is_path (bool, optional): if ```True``` check if the path is exist. Defaults to False.
        prerequest (list or str, optional): a list of field name that are prerequestedby the target field name.
            Defaults to ```[]```.
        enum_list (list, optional): list of possible values for the target field. Defaults to None.
        max_val (float, optional): maximum possible value for the target field. Defaults to None.
        min_val (float, optional): minimum possible value for the target field. Defaults to None.
        restricted (bool, optional): if ```True``` the target field has to be defined. Defaults to False.
        alternative (str, optional): a field name superceding the target field. Defaults to None.
        allow_none (bool, optional): if ```True``` allow the target field to be ```None```. Defaults to False.


    Example:
        >>> num_mels = 5
        >>> check_argument('num_mels', c, restricted=True, min_val=10, max_val=2056)
        >>> fft_size = 128
        >>> check_argument('fft_size', c, restricted=True, min_val=128, max_val=4058)
    """
    # check if None allowed
    if c[name] is None:
        if allow_none:
            return
        msg = f" [!] None value is not allowed for {name}."
        raise TypeError(msg)
    # check if restricted and it it is check if it exists
    if isinstance(restricted, bool) and restricted and name not in c:
        msg = f" [!] {name} not defined in config.json"
        raise KeyError(msg)
    # check prerequest fields are defined
    if isinstance(prerequest, list):
        if any(f not in c for f in prerequest):
            msg = f" [!] prequested fields {prerequest} for {name} are not defined."
            raise KeyError(msg)
    elif prerequest is not None and prerequest not in c:
        msg = f" [!] prequested field {prerequest} for {name} is not defined."
        raise KeyError(msg)
    # check if the path exists
    if is_path and not Path(c[name]).exists():
        msg = f' [!] path for {name} ("{c[name]}") does not exist.'
        raise FileNotFoundError(msg)
    # skip the rest if the alternative field is defined.
    if alternative is not None and alternative in c and c[alternative] is not None:
        return
    # check value constraints
    if name in c:
        if max_val is not None and c[name] > max_val:
            msg = f" [!] {name} is larger than max value {max_val}"
            raise ValueError
        if min_val is not None and c[name] < min_val:
            msg = f" [!] {name} is smaller than min value {min_val}"
            raise ValueError
        if enum_list is not None and c[name].lower() not in enum_list:
            msg = f" [!] {name} is not a valid value"
            raise ValueError
