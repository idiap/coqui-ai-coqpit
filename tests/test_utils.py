from typing import Union

from coqpit.coqpit import _is_optional_field, _is_union, _is_union_and_not_simple_optional

# TODO: `type: ignore` can probably be removed when switching to Python 3.10
#       Union syntax (e.g. str | int)


def test_is_union() -> None:
    cases = (
        (Union[str, int], True),
        (Union[str, None], True),
        (int, False),
        (list[int], False),
        (list[str | int], False),
    )
    for item, expected in cases:
        assert _is_union(item) == expected  # type: ignore[arg-type]


def test_is_union_and_not_simple_optional() -> None:
    cases = (
        (Union[str, int], True),
        (Union[str, None], False),
        (Union[list[int], None], False),
        (int, False),
        (list[int], False),
        (list[str | int], False),
    )
    for item, expected in cases:
        assert _is_union_and_not_simple_optional(item) == expected  # type: ignore[arg-type]


def test_is_optional_field() -> None:
    cases = (
        (Union[str, int], False),
        (Union[str, None], True),
        (Union[list[int], None], True),
        (int, False),
        (list[int], False),
        (list[str | int], False),
    )
    for item, expected in cases:
        assert _is_optional_field(item) == expected  # type: ignore[arg-type]
