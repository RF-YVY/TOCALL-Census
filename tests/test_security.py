from app.aprs import AprsIsClient
from app.main import client, public_settings, status_payload


async def noop_packet(_packet):
    return None


async def noop_status(_state, _message):
    return None


def test_aprs_client_does_not_expose_passcode_in_public_settings() -> None:
    aprs_client = AprsIsClient(on_packet=noop_packet, on_status=noop_status)
    aprs_client.settings = {
        "server": "rotate.aprs2.net",
        "port": 14580,
        "callsign": "N0CALL",
        "filter": "t/p",
    }

    assert "passcode" not in aprs_client.settings


def test_status_payload_masks_passcode() -> None:
    original_settings = dict(client.settings)
    try:
        client.settings = {
            "server": "rotate.aprs2.net",
            "port": 14580,
            "callsign": "N0CALL",
            "filter": "t/p",
        }

        assert public_settings()["passcode"] == "masked"
        assert status_payload()["settings"]["passcode"] == "masked"
        assert "-1" not in str(status_payload())
    finally:
        client.settings = original_settings
