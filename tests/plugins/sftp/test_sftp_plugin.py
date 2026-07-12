from SocketMock.plugins.sftp import SFTPPlugin
from SocketMock.plugins.sftp.stubs import StubStore


def test_sftp_plugin_defaults() -> None:
    plugin = SFTPPlugin()
    assert plugin.name == "sftp"
    assert plugin.default_port == 2222


def test_sftp_stub_store_matches_operation_and_path() -> None:
    store = StubStore()
    store.add(
        {
            "request": {"operation": "open", "path": {"equalTo": "/tmp/example.txt"}},
            "response": {"statusCode": 2, "message": "not found"},
        }
    )

    assert store.find_match({"operation": "open", "path": "/tmp/example.txt"}) is not None
    assert store.find_match({"operation": "open", "path": "/tmp/other.txt"}) is None


def test_sftp_stub_store_matches_flags() -> None:
    store = StubStore()
    store.add(
        {
            "request": {
                "operation": "open",
                "path": {"regex": r"^/tmp/.*"},
                "flags": {"equalTo": 5},
            },
            "response": {"statusCode": 3, "message": "permission denied"},
        }
    )

    stub = store.find_match({"operation": "open", "path": "/tmp/data", "pflags": 5})
    assert stub is not None
    assert stub.response["statusCode"] == 3
