from dataclasses import dataclass, field

import pytest

from coqpit import Coqpit


@dataclass
class Person(Coqpit):
    name: str | None = None
    age: int | None = None


@dataclass
class Reference(Coqpit):
    name: str = "Coqpit"
    size: int = 3
    people: list[Person] = field(
        default_factory=lambda: [
            Person(name="Eren", age=11),
            Person(name="Geren", age=12),
            Person(name="Ceren", age=15),
        ],
    )
    people_ids: list[int] = field(default_factory=lambda: [1, 2, 3])


@dataclass
class WithRequired(Coqpit):
    name: str


def test_new_from_dict() -> None:
    ref_config = Reference(name="Fancy", size=3**10, people=[Person(name="Anonymous", age=42)])

    new_config = Reference.new_from_dict({"name": "Fancy", "size": 3**10, "people": [{"name": "Anonymous", "age": 42}]})

    # check values
    assert len(ref_config) == len(new_config)
    assert ref_config.name == new_config.name
    assert ref_config.size == new_config.size
    assert ref_config.people[0].name == new_config.people[0].name
    assert ref_config.people[0].age == new_config.people[0].age

    with pytest.raises(ValueError, match="Missing required field"):
        WithRequired.new_from_dict({})
