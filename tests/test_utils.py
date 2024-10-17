from coqpit.coqpit import _deserialize_primitive_types


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
