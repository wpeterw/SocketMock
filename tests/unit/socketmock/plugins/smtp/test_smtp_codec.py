from socketmock.plugins.smtp.codec import SMTPCodec, SMTPMessage


def test_smtp_codec_parses_and_serializes_message() -> None:
    parsed = SMTPCodec.parse_message(["Subject: hello", "", "body"])
    assert parsed.headers["Subject"] == "hello"
    assert parsed.body == "body"

    serialized = SMTPCodec.serialize_message(
        SMTPMessage(
            from_addr="alice@example.com",
            recipients=["bob@example.com"],
            headers={"Subject": "hello"},
            body="body",
        )
    )
    assert "From: alice@example.com" in serialized
    assert "To: bob@example.com" in serialized
    assert "Subject: hello" in serialized
    assert "body" in serialized

    assert SMTPCodec.parse_command("HELO localhost") == ("HELO", "localhost")
    assert SMTPCodec.build_response(250, "ok") == "250 ok"
    assert SMTPCodec.build_banner("socketmock") == "220 socketmock ESMTP ready"
