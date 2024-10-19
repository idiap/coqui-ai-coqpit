from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from coqpit import Coqpit


@dataclass
class Person(Coqpit):
    name: Optional[str] = None
    age: Optional[int] = None


@dataclass
class Group(Coqpit):
    name: Optional[str] = None
    size: Optional[int] = None
    path: Optional[Path] = None
    people: list[Person] = field(default_factory=list)
    some_dict: dict[str, Optional[int]] = field(default_factory=dict)


@dataclass
class Reference(Coqpit):
    name: Optional[str] = "Coqpit"
    size: Optional[int] = 3
    path: Path = Path("a/b")
    people: list[Person] = field(
        default_factory=lambda: [
            Person(name="Eren", age=11),
            Person(name="Geren", age=12),
            Person(name="Ceren", age=15),
        ]
    )
    some_dict: dict[str, Optional[int]] = field(default_factory=lambda: {"a": 1, "b": 2, "c": None})


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
