from dataclasses import dataclass, field
from pathlib import Path

import pytest

from coqpit.coqpit import Coqpit, _deserialize_list, _deserialize_primitive_types


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


def test_deserialize_list() -> None:
    assert _deserialize_list([1, 2, 3], list) == [1, 2, 3]
    assert _deserialize_list([1, 2, 3], list[int]) == [1, 2, 3]
    assert _deserialize_list([1, 2, 3], list[float]) == [1.0, 2.0, 3.0]
    assert _deserialize_list([1, 2, 3], list[str]) == ["1", "2", "3"]


def test_deserialize_primitive_type() -> None:
    cases = (
        (True, bool, True),
        (False, bool, False),
        ("a", str, "a"),
        ("3", str, "3"),
        (3, int, 3),
        (3, float, 3.0),
        (3, str, "3"),
        (3.0, str, "3.0"),
        (3, bool, True),
        ("a", str | None, "a"),
        ("3", str | None, "3"),
        (3, int | None, 3),
        (3, float | None, 3.0),
        (None, str | None, None),
        (None, int | None, None),
        (None, float | None, None),
        (None, str | None, None),
        (float("inf"), float, float("inf")),
        (float("inf"), int, float("inf")),
        (float("-inf"), float, float("-inf")),
        (float("-inf"), int, float("-inf")),
    )
    for value, field_type, expected in cases:
        assert _deserialize_primitive_types(value, field_type) == expected

    with pytest.raises(TypeError):
        _deserialize_primitive_types(3, Coqpit)
