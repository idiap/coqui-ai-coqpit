import sys
from dataclasses import dataclass, field

import pytest

from coqpit.coqpit import Coqpit, Serializable


@dataclass
class Inner(Coqpit):
    x: int = 1


@dataclass
class Config(Coqpit):
    a: int = 1
    b: str = "b"
    c: float | None = None
    inner: Inner = field(default_factory=Inner)


@dataclass
class ContractConfig(Coqpit):
    a: int = field(default=1, metadata={"contract": lambda x: x > 0})


@dataclass
class Plain(Serializable):
    a: int = 1
    inner: Inner = field(default_factory=Inner)


def test_serializable_to_dict_is_shallow() -> None:
    config = Plain(a=2)
    d = config.to_dict()
    assert d == {"a": 2, "inner": config.inner}
    assert d["inner"] is config.inner


def test_coqpit_to_dict_serializes() -> None:
    assert Config(a=2).to_dict() == {"a": 2, "b": "b", "c": None, "inner": {"x": 1}}


def test_items() -> None:
    config = Config(a=2)
    assert dict(config.items()) == {"a": 2, "b": "b", "c": None, "inner": {"x": 1}}


def test_delitem() -> None:
    config = Config(a=2)
    del config["a"]
    assert "a" not in vars(config)
    # Falls back to the class-level default
    assert config.a == 1


def test_update_from_dict() -> None:
    config = Config()
    config.update({"a": 2, "b": "x"})
    assert config.a == 2
    assert config.b == "x"


def test_update_from_mapping_with_keys() -> None:
    config = Config()
    config.update(Config(a=3, b="y"))
    assert config.a == 3
    assert config.b == "y"


def test_update_from_iterable() -> None:
    config = Config()
    config.update([("a", 4), ("c", 0.5)])
    assert config.a == 4
    assert config.c == pytest.approx(0.5)


def test_update_from_kwargs() -> None:
    config = Config()
    config.update({"a": 5}, b="z")
    assert config.a == 5
    assert config.b == "z"
    config.update(c=1.5)
    assert config.c == pytest.approx(1.5)


def test_validate() -> None:
    Config(a=2, c=0.5).validate()


def test_validate_round_trip_mismatch() -> None:
    config = Config()
    config.a = "not an int"  # ty: ignore[invalid-assignment]
    with pytest.warns(UserWarning, match="Type mismatch"), pytest.raises(ValueError, match="could not be deserialized"):
        config.validate()


def test_validate_not_optional() -> None:
    config = Config()
    config.a = None  # ty: ignore[invalid-assignment]
    with pytest.raises(TypeError, match="a is not optional"):
        config.validate()


def test_validate_contract() -> None:
    ContractConfig(a=1).validate()
    config = ContractConfig()
    config.a = -1
    with pytest.raises(ValueError, match="break the contract for a"):
        config.validate()


def test_init_from_argparse_sys_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["prog", "--coqpit.a", "7", "--coqpit.inner.x", "8"])
    config = Config.init_from_argparse()
    assert config.a == 7
    assert config.inner.x == 8


def test_parse_args_sys_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["prog", "--coqpit.b", "argv"])
    config = Config()
    config.parse_args()
    assert config.b == "argv"


def test_parse_known_args_sys_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["prog", "--coqpit.a", "9", "--unknown", "1"])
    config = Config()
    unknown = config.parse_known_args()
    assert config.a == 9
    assert unknown == ["--unknown", "1"]
