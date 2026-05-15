from app.main import app_settings, saved_passcode_if_masked
from app.settings import AppSettings


def test_settings_persist_filter_and_mask_passcode(tmp_path) -> None:
    path = tmp_path / "settings.json"
    settings = AppSettings(path)
    settings.update(
        {
            "filter": "r/0/0/9999",
            "server": "rotate.aprs2.net",
            "port": 14580,
            "callsign": "N0CALL",
            "passcode": "-1",
            "target_tocall": "APRSPV",
        }
    )

    reloaded = AppSettings(path)

    assert reloaded.values["filter"] == "r/0/0/9999"
    assert reloaded.values["target_tocall"] == "APRSPV"
    assert reloaded.public()["passcode"] == "masked"


def test_masked_passcode_preserves_saved_secret() -> None:
    original = app_settings.values.get("passcode")
    try:
        app_settings.values["passcode"] = "12345"
        assert saved_passcode_if_masked("masked") == "12345"
        assert saved_passcode_if_masked("-1") == "-1"
    finally:
        app_settings.values["passcode"] = original
