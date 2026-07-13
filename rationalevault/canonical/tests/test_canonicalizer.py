from rationalevault.canonical.canonicalizer import canonicalize


def test_canonicalize_dict_sorts_keys():
    result = canonicalize({"z": 1, "a": 2})
    assert list(result.keys()) == ["a", "z"]


def test_canonicalize_nested_dict():
    result = canonicalize({"b": {"z": 1, "a": 2}})
    assert list(result["b"].keys()) == ["a", "z"]


def test_canonicalize_string_nfc():
    result = canonicalize({"key": "caf\u0065\u0301"})
    assert result["key"] == "caf\u00e9"


def test_canonicalize_list_preserves_order():
    result = canonicalize({"items": [3, 1, 2]})
    assert result["items"] == [3, 1, 2]


def test_canonicalize_int():
    result = canonicalize({"n": 42})
    assert result["n"] == 42


def test_canonicalize_float():
    result = canonicalize({"n": 0.5})
    assert result["n"] == 0.5


def test_canonicalize_bool():
    result = canonicalize({"flag": True})
    assert result["flag"] is True


def test_canonicalize_none():
    result = canonicalize({"val": None})
    assert result["val"] is None


def test_canonicalize_deep_nesting():
    result = canonicalize({"a": {"b": {"c": {"z": 1, "a": 2}}}})
    assert list(result["a"]["b"]["c"].keys()) == ["a", "z"]
