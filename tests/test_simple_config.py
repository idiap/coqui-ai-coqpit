from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from coqpit.coqpit import MISSING, Coqpit, check_argument


@dataclass
class SimpleConfig(Coqpit):
    val_a: int = 10
    val_b: int | None = None
    val_d: float = 10.21
    val_c: str = "Coqpit is great!"
    vol_e: bool = True
    # mandatory field
    # raise an error when accessing the value if it is not changed. It is a way to define
    val_k: int = MISSING
    # optional field
    val_dict: dict[str, Any] = field(default_factory=lambda: {"val_aa": 10, "val_ss": "This is in a dict."})
    # list of list
    val_listoflist: list[list[int]] = field(default_factory=lambda: [[1, 2], [3, 4]])
    val_listofunion: list[list[str | int | bool]] = field(
        default_factory=lambda: [[1, 3], [1, "Hi!"], [True, False]],
    )

    def check_values(
        self,
    ) -> None:  # you can define explicit constraints on the fields using `check_argument()`
        """Check config fields"""
        c = asdict(self)
        check_argument("val_a", c, restricted=True, min_val=10, max_val=2056)
        check_argument("val_b", c, restricted=True, min_val=128, max_val=4058, allow_none=True)
        check_argument("val_c", c, restricted=True)


def test_simple_config() -> None:
    file_path = Path(__file__).resolve().parent / "example_config.json"
    config = SimpleConfig()

    assert config._is_initialized()

    # try MISSING class argument
    try:
        _ = config.val_k
    except AttributeError:
        print(" val_k needs a different value before accessing it.")
    config.val_k = 1000

    assert "val_a" in config
    assert config.has("val_a")

    # try serialization and deserialization
    print(config.serialize())
    print(config.to_json())
    config.save_json(file_path)
    config.load_json(file_path)
    config.pprint()

    # try `dict` interface
    print(*config)
    print(dict(**config))

    # value assignment by mapping
    # TODO: MAYBE this should raise an errorby the value check.
    config["val_a"] = -999
    print(config["val_a"])
    assert config.val_a == -999
