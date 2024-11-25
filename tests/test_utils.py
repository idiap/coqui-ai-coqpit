from coqpit.coqpit import _is_optional_field, _is_union, _is_union_and_not_simple_optional


def test_is_union() -> None:
    cases = (
        (str | int, True),
        (str | None, True),
        (int, False),
        (list[int], False),
        (list[str | int], False),
    )
    for item, expected in cases:
        assert _is_union(item) == expected


def test_is_union_and_not_simple_optional() -> None:
    cases = (
        (str | int, True),
        (str | None, False),
        (list[int] | None, False),
        (int, False),
        (list[int], False),
        (list[str | int], False),
    )
    for item, expected in cases:
        assert _is_union_and_not_simple_optional(item) == expected


def test_is_optional_field() -> None:
    cases = (
        (str | int, False),
        (str | None, True),
        (list[int] | None, True),
        (int, False),
        (list[int], False),
        (list[str | int], False),
    )
    for item, expected in cases:
        assert _is_optional_field(item) == expected
