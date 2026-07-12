import pytest

from SocketMock.plugins.smpp import codec as smpp_codec


def test_smpp_codec_round_trip_and_extract() -> None:
    pdu = {
        "command_name": "bind_transceiver",
        "sequence_number": 7,
        "command_status": 0,
        "system_id": "sys",
        "password": "pwd",
        "system_type": "",
        "interface_version": 0x34,
        "addr_ton": 1,
        "addr_npi": 2,
        "address_range": "",
    }
    raw = smpp_codec.encode_pdu(pdu)
    decoded = smpp_codec.decode_pdu(raw)
    assert decoded["command_name"] == "bind_transceiver"
    assert decoded["system_id"] == "sys"
    assert decoded["sequence_number"] == 7

    submit = {
        "command_name": "submit_sm",
        "sequence_number": 8,
        "service_type": "",
        "source_addr_ton": 1,
        "source_addr_npi": 1,
        "source_addr": "src",
        "dest_addr_ton": 1,
        "dest_addr_npi": 1,
        "destination_addr": "dst",
        "esm_class": 0,
        "protocol_id": 0,
        "priority_flag": 0,
        "schedule_delivery_time": "",
        "validity_period": "",
        "registered_delivery": 0,
        "replace_if_present_flag": 0,
        "data_coding": 0,
        "sm_default_msg_id": 0,
        "short_message": b"hello",
        "tlvs": {0x0101: b"x"},
    }
    raw_submit = smpp_codec.encode_pdu(submit)
    decoded_submit = smpp_codec.decode_pdu(raw_submit)
    assert decoded_submit["short_message"] == b"hello"
    assert decoded_submit["tlvs"][0x0101] == b"x"

    partial = bytearray(raw_submit[:-2])
    pdu_out, consumed = smpp_codec.try_extract_one(partial)
    assert pdu_out is None
    assert consumed == 0

    parsed, consumed = smpp_codec.try_extract_one(bytearray(raw_submit))
    assert parsed is not None
    assert consumed == len(raw_submit)

    with pytest.raises(smpp_codec.PDUParseError):
        smpp_codec.try_extract_one(bytearray(b"\x00\x00\x00\x00"))
