from __future__ import annotations

from libs.stubs import StubStore as BaseStubStore


class StubStore(BaseStubStore):
    def __init__(self) -> None:
        super().__init__(matcher=lambda _request, _pdu: True)
