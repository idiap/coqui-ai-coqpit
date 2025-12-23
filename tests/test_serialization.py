from dataclasses import dataclass, field
from pathlib import Path
from types import UnionType
from typing import Any, Literal

import pytest

from coqpit.coqpit import (
    Coqpit,
    FieldType,
    _deserialize_list,
    _deserialize_literal,
    _deserialize_primitive_types,
    _deserialize_union,
)


@dataclass
class Person(Coqpit):
    name: str | None = None
    age: int | None = None


@dataclass
class Group(Coqpit):
    name: str | None = None
    size: int | None = None
    path: Path | None = None
    people: list[Person] = field(default_factory=list)
    some_dict: dict[str, int | None] = field(default_factory=dict)


@dataclass
class Reference(Coqpit):
    name: str | None = "Coqpit"
    size: int | None = 3
    path: Path = Path("a/b")
    people: list[Person] = field(
        default_factory=lambda: [
            Person(name="Eren", age=11),
            Person(name="Geren", age=12),
            Person(name="Ceren", age=15),
        ],
    )
    some_dict: dict[str, int | None] = field(default_factory=lambda: {"a": 1, "b": 2, "c": None})


def test_serialization() -> None:
    file_path = Path(__file__).resolve().parent / "test_serialization.json"

    ref_config = Reference()
    ref_config.save_json(file_path)

    new_config = Group()
    new_config.load_json(file_path)
    new_config.pprint()

    # check values
    assert len(ref_config) == len(new_config)
    assert ref_config.name == new_config.name
    assert ref_config.size == new_config.size
    assert ref_config.people[0].name == new_config.people[0].name
    assert ref_config.people[1].name == new_config.people[1].name
    assert ref_config.people[2].name == new_config.people[2].name
    assert ref_config.people[0].age == new_config.people[0].age
    assert ref_config.people[1].age == new_config.people[1].age
    assert ref_config.people[2].age == new_config.people[2].age
    assert ref_config.path == new_config.path
    assert ref_config.some_dict["a"] == new_config.some_dict["a"]
    assert ref_config.some_dict["b"] == new_config.some_dict["b"]
    assert ref_config.some_dict["c"] == new_config.some_dict["c"]


def test_serialization_type_mismatch() -> None:
    file_path = Path(__file__).resolve().parent / "test_serialization.json"

    ref_config = Reference()
    ref_config.size = True
    ref_config.save_json(file_path)

    new_config = Group()
    with pytest.warns(UserWarning, match="Type mismatch"):
        new_config.load_json(file_path)
    new_config.pprint()

    # check values
    assert len(ref_config) == len(new_config)
    assert new_config.size is None


def test_deserialize_list() -> None:
    assert _deserialize_list([1, 2, 3], list) == [1, 2, 3]
    assert _deserialize_list([1, 2, 3], list[int]) == [1, 2, 3]
    assert _deserialize_list([[1, 2, 3]], list[list[int]]) == [[1, 2, 3]]
    assert _deserialize_list([1.0, 2.0, 3.0], list[float]) == [1.0, 2.0, 3.0]
    assert _deserialize_list([1, 2, 3], list[float]) == [1.0, 2.0, 3.0]
    assert _deserialize_list(["1", "2", "3"], list[str]) == ["1", "2", "3"]

    with pytest.raises(TypeError, match="does not match field type"):
        _deserialize_list([1, 2, 3], list[list[int]])


@pytest.mark.parametrize(
    ("value", "field_type", "expected"),
    [
        (True, bool, True),
        (False, bool, False),
        ("a", str, "a"),
        ("3", str, "3"),
        (3, int, 3),
        (3, float, 3.0),
        ("a", str | None, "a"),
        ("3", str | None, "3"),
        (3, int | None, 3),
        (3, float | None, 3.0),
        (None, str | None, None),
        (None, int | None, None),
        (None, float | None, None),
        (None, bool | None, None),
        (float("inf"), float, float("inf")),
        (float("inf"), int, float("inf")),
        (float("-inf"), float, float("-inf")),
        (float("-inf"), int, float("-inf")),
    ],
)
def test_deserialize_primitive_type(
    value: str | bool | float | None,
    field_type: FieldType,
    expected: str | bool | float | None,
) -> None:
    assert _deserialize_primitive_types(value, field_type) == expected


@pytest.mark.parametrize(
    ("value", "field_type"),
    [
        (3, str),
        (3, str | None),
        (3.0, str),
        (3, bool),
        ("1", int),
        ("2.0", float),
        ("True", bool),
        ("True", bool | None),
        ("", bool | None),
        ([1, 2], str),
        ([1, 2, 3], int),
    ],
)
def test_deserialize_primitive_type_mismatch(
    value: str | bool | float | None,
    field_type: FieldType,
) -> None:
    with pytest.raises(TypeError, match="does not match field type"):
        _deserialize_primitive_types(value, field_type)


@pytest.mark.parametrize(
    ("value", "field_type", "expected"),
    [
        ("a", int | str, "a"),
        ("a", str | int, "a"),
        (1, int | str, 1),
        (1, str | int, 1),
        (1, str | int | list[int], 1),
        ([1, 2], str | int | list[int], [1, 2]),
        ([1, 2], list[int] | int | str, [1, 2]),
        ([1, 2], dict | list, [1, 2]),
        (["a", "b"], list[str] | list[list[str]], ["a", "b"]),
        (["a", "b"], list[list[str]] | list[str], ["a", "b"]),
        ([["a", "b"]], list[str] | list[list[str]], [["a", "b"]]),
        ([["a", "b"]], list[list[str]] | list[str], [["a", "b"]]),
    ],
)
def test_deserialize_union(value: Any, field_type: UnionType, expected: Any) -> None:
    assert _deserialize_union(value, field_type) == expected


@pytest.mark.parametrize(
    ("value", "field_type", "expected"),
    [
        ("a", Literal["a", "b", "c"], "a"),
        ("b", Literal["a", "b", "c"], "b"),
        ("c", Literal["a", "b", "c"], "c"),
        (1, Literal[1, 2, 3], 1),
        (2, Literal[1, 2, 3], 2),
        (3, Literal[1, 2, 3], 3),
        (True, Literal[True, False], True),
        (False, Literal[True, False], False),
        ("a", Literal["a", 1, True], "a"),
        (1, Literal["a", 1, True], 1),
        (True, Literal["a", 1, True], True),
    ],
)
def test_deserialize_literal(value: Any, field_type: FieldType, expected: Any) -> None:
    assert _deserialize_literal(value, field_type) == expected


@pytest.mark.parametrize(
    ("value", "field_type"),
    [
        ("d", Literal["a", "b", "c"]),
        ("x", Literal["a", "b", "c"]),
        (4, Literal[1, 2, 3]),
        (0, Literal[1, 2, 3]),
        ("a", Literal[1, 2, 3]),
        (1, Literal["a", "b", "c"]),
        (None, Literal["a", "b", "c"]),
        (False, Literal["a", 1]),
        (2, Literal["a", 1, True]),
    ],
)
def test_deserialize_literal_mismatch(value: Any, field_type: FieldType) -> None:
    with pytest.raises(TypeError, match="not valid for Literal field type"):
        _deserialize_literal(value, field_type)
