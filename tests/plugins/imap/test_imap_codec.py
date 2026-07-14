from socketmock.plugins.imap.codec import IMAPCodec


def test_imap_codec_helpers() -> None:
    tag, verb, arg = IMAPCodec.parse_command('a001 LOGIN "user" password')
    assert tag == "a001"
    assert verb == "LOGIN"
    assert arg == '"user" password'

    assert IMAPCodec.build_tagged("a001", "OK", "LOGIN completed") == "a001 OK LOGIN completed"
    assert IMAPCodec.build_list_response() == '* LIST (\\HasNoChildren) "/" "INBOX"'

    lines = IMAPCodec.build_fetch_response(1, "hello")
    assert lines == ["* 1 FETCH (BODY[TEXT] {5}", "hello", ")"]
