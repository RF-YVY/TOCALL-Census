from app.aprs import classify_transport, parse_packet, server_comment_status


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
