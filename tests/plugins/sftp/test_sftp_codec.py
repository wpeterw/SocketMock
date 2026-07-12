from pathlib import Path

from SocketMock.plugins.sftp import codec as sftp_codec


def test_sftp_codec_helpers(tmp_path: Path) -> None:
    data_path = tmp_path / "demo.txt"
    data_path.write_text("hello", encoding="utf-8")

    packet = sftp_codec.encode_packet(sftp_codec.SSH_FXP_OPEN, b"abc")
    assert sftp_codec.decode_packet(packet) == (sftp_codec.SSH_FXP_OPEN, b"abc")
    assert sftp_codec.decode_packet(packet[:-1]) is None

    assert sftp_codec.unpack_u32(b"\x00\x00\x00\x02") == (2, 4)
    assert sftp_codec.unpack_u64(b"\x00\x00\x00\x00\x00\x00\x00\x03") == (3, 8)
    assert sftp_codec.unpack_string(b"\x00\x00\x00\x05hello") == ("hello", 9)

    attrs_payload = sftp_codec.encode_attrs(str(data_path))
    attrs, offset = sftp_codec.decode_attrs(attrs_payload)
    assert attrs["size"] == 5
    assert offset == len(attrs_payload)

    name_payload = sftp_codec.encode_name(7, [("demo.txt", "demo.txt", attrs_payload)])
    request_id, _ = sftp_codec.unpack_u32(name_payload)
    assert request_id == 7
