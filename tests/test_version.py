from app.main import is_newer_version, normalize_version


def test_normalize_version_removes_v_prefix() -> None:
    assert normalize_version("v0.3.0") == "0.3.0"
    assert normalize_version(" V1.2.0 ") == "1.2.0"


def test_is_newer_version_compares_semver_parts() -> None:
    assert is_newer_version("v1.0.1", "v1.0.0") is True
    assert is_newer_version("v1.0.0", "v1.0.0") is False
    assert is_newer_version("v0.9.9", "v1.0.0") is False
    assert is_newer_version("v2.0", "v1.0.0") is True
