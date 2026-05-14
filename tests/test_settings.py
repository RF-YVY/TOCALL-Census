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
