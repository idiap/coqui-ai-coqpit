import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypeVar

import pytest

from coqpit.coqpit import MISSING, Coqpit, _deserialize, _deserialize_list, check_argument


@dataclass
class Person(Coqpit):
    name: str = "a"


@dataclass
class Config(Coqpit):
    a: int = 1


T = TypeVar("T")


# Deserialization


def test_deserialize_string_type_hint() -> None:
    with pytest.raises(NotImplementedError, match="Strings as type hints"):
        _deserialize(1, "int")


def test_deserialize_unsupported_type() -> None:
    with pytest.raises(TypeError, match="does not match declared"):
        _deserialize({1, 2}, set[int])


def test_deserialize_list_multi_type() -> None:
    with pytest.raises(ValueError, match="multi-type hinted"):
        _deserialize_list([1], list[int, str])  # ty: ignore[invalid-type-arguments]


def test_deserialize_list_typevar() -> None:
    assert _deserialize_list([1, 2], list[T]) == [1, 2]


def test_deserialize_not_a_dict() -> None:
    with pytest.raises(TypeError):
        Config().deserialize([1])  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError):
        Config.deserialize_immutable([1])  # ty: ignore[invalid-argument-type]


def test_deserialize_missing_value() -> None:
    with pytest.raises(ValueError, match="unknown value for a"):
        Config().deserialize({"a": MISSING})
    with pytest.raises(ValueError, match="unknown value for a"):
        Config.deserialize_immutable({"a": MISSING})


# Argparse


def _init_argparse(field_type: Any, default: Any = None, *, relaxed_parser: bool = False) -> argparse.ArgumentParser:
    @dataclass
    class C(Coqpit):
        f: field_type = default

    return C.init_argparse(relaxed_parser=relaxed_parser)


def _init_argparse_factory(field_type: Any, factory: Any, *, relaxed_parser: bool = False) -> argparse.ArgumentParser:
    @dataclass
    class C(Coqpit):
        f: field_type = field(default_factory=factory)

    return C.init_argparse(relaxed_parser=relaxed_parser)


def test_argparse_string_type_hint() -> None:
    with pytest.raises(NotImplementedError, match="Strings as type hints"):
        _init_argparse("int", 1)


def test_argparse_multi_type_list() -> None:
    with pytest.raises(ValueError, match="multi-type hinted"):
        _init_argparse(list[int, str])  # ty: ignore[invalid-type-arguments]


def test_argparse_unhinted_list() -> None:
    with pytest.raises(ValueError, match="un-hinted"):
        _init_argparse(list)


@pytest.mark.parametrize("field_type", [list[Person], Person | list[Person]])
def test_argparse_empty_non_primitive_list(field_type: Any) -> None:
    with pytest.raises(NotImplementedError, match="non primitive inner type"):
        _init_argparse_factory(field_type, list)
    _init_argparse_factory(field_type, list, relaxed_parser=True)


def test_argparse_union() -> None:
    with pytest.raises(NotImplementedError, match="Parsing `Union` field"):
        _init_argparse(int | str, 1)
    _init_argparse(int | str, 1, relaxed_parser=True)


def test_argparse_mixed_literal() -> None:
    with pytest.raises(TypeError, match="Mixing literals"):
        _init_argparse(Literal[1, "a"], 1)


def test_argparse_unsupported_type() -> None:
    with pytest.raises(NotImplementedError, match="is not supported by arg_parser"):
        _init_argparse(bytes, b"a")
    _init_argparse(bytes, b"a", relaxed_parser=True)


def test_parse_args_unknown_field() -> None:
    config = Config()
    with pytest.raises(TypeError, match="'b' not exist"):
        config.parse_args(argparse.Namespace(**{"coqpit.b": 1}))


# check_argument


def test_check_argument_none() -> None:
    check_argument("a", {"a": None})
    with pytest.raises(TypeError, match="None value is not allowed"):
        check_argument("a", {"a": None}, allow_none=False)


def test_check_argument_restricted_missing() -> None:
    with pytest.raises(KeyError):
        check_argument("a", {}, restricted=True)


def test_check_argument_prerequest() -> None:
    c = {"a": 1, "b": 2}
    check_argument("a", c, prerequest="b")
    check_argument("a", c, prerequest=["b"])
    with pytest.raises(KeyError, match="prequested field c"):
        check_argument("a", c, prerequest="c")
    with pytest.raises(KeyError, match="prequested fields"):
        check_argument("a", c, prerequest=["b", "c"])


def test_check_argument_path(tmp_path: Path) -> None:
    check_argument("p", {"p": tmp_path}, is_path=True)
    with pytest.raises(FileNotFoundError, match="path for p"):
        check_argument("p", {"p": tmp_path / "missing"}, is_path=True)


def test_check_argument_values() -> None:
    c = {"a": 5, "s": "B"}
    check_argument("a", c, min_val=5, max_val=5)
    check_argument("s", c, enum_list=["a", "b"])
    with pytest.raises(ValueError, match="larger than max value"):
        check_argument("a", c, max_val=4)
    with pytest.raises(ValueError, match="smaller than min value"):
        check_argument("a", c, min_val=6)
    with pytest.raises(ValueError, match="not a valid value"):
        check_argument("s", c, enum_list=["c"])


def test_check_argument_alternative() -> None:
    c = {"a": 5, "b": 1}
    check_argument("a", c, max_val=4, alternative="b")
    with pytest.raises(ValueError, match="larger than max value"):
        check_argument("a", {"a": 5, "b": None}, max_val=4, alternative="b")
