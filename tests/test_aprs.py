import asyncio

from app.aprs import (
    AprsIsClient,
    AprsIsConnectionDropped,
    LoginRejectedError,
    RECONNECT_DELAY_SECONDS,
    classify_transport,
    parse_packet,
    server_comment_status,
)


def test_parse_tocall_between_greater_than_and_comma() -> None:
    packet = parse_packet("N6PAZ-1>APDW16,WIDE1-1,WIDE2-1,qAR,N6PAZ-2:!3401.00N/08901.00W>")

    assert packet is not None
    assert packet.source == "N6PAZ-1"
    assert packet.tocall == "APDW16"
    assert packet.transport == "rf_igate"
    assert packet.lat == 34.016667
    assert packet.lon == -89.016667


def test_parse_aprs_propview_position_packet() -> None:
    packet = parse_packet(
        "KD2FMW-1>APRSPV,TCPIP*,qAC,T2RDU:=4006.34N/07447.02W#Alinco DR135 APRS PropView Digi/IGate"
    )

    assert packet is not None
    assert packet.source == "KD2FMW-1"
    assert packet.tocall == "APRSPV"
    assert packet.transport == "aprs_is"
    assert packet.lat == 40.105667
    assert packet.lon == -74.783667


def test_parse_tocall_without_path() -> None:
    packet = parse_packet("CALL>APRS:>status")

    assert packet is not None
    assert packet.tocall == "APRS"
    assert packet.path == ""


def test_ignores_server_comments() -> None:
    assert parse_packet("# aprsc server greeting") is None


def test_transport_classification() -> None:
    assert classify_transport("WIDE1-1,qAR,IGATE") == "rf_igate"
    assert classify_transport("TCPIP*,qAC,T2SERVER") == "aprs_is"
    assert classify_transport("WIDE1-1,WIDE2-1") == "rf_path"


def test_server_comment_status_explains_rejected_login() -> None:
    state, message = server_comment_status("# server: Login by user not allowed")

    assert state == "rejected"
    assert "APRS-IS rejected the login" in message
    assert "callsign/passcode" in message


def test_dropped_live_connection_reconnects_quickly(monkeypatch) -> None:
    statuses: list[tuple[str, str]] = []
    sleep_delays: list[int] = []

    async def noop_packet(_packet):
        return None

    async def record_status(state: str, message: str) -> None:
        statuses.append((state, message))

    async def fake_sleep(delay: int) -> None:
        sleep_delays.append(delay)

    class ScriptedClient(AprsIsClient):
        def __init__(self) -> None:
            super().__init__(on_packet=noop_packet, on_status=record_status)
            self.attempts = 0

        async def _connect_once(self) -> None:
            self.attempts += 1
            if self.attempts == 1:
                raise AprsIsConnectionDropped("APRS-IS server closed the connection")
            raise LoginRejectedError("stop test loop")

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    client = ScriptedClient()
    asyncio.run(client._run())

    assert client.attempts == 2
    assert sleep_delays == [RECONNECT_DELAY_SECONDS]
    assert statuses[0] == ("reconnecting", "APRS-IS server closed the connection; reconnecting")
