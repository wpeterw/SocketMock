from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IMAPMessage:
    sequence: int
    body: str


class IMAPCodec:
    @staticmethod
    def parse_command(command: str) -> tuple[str, str, str]:
        parts = command.split(maxsplit=2)
        tag = parts[0] if parts else "A000"
        verb = parts[1].upper() if len(parts) > 1 else ""
        arg = parts[2] if len(parts) > 2 else ""
        return tag, verb, arg

    @staticmethod
    def build_tagged(tag: str, status: str, message: str) -> str:
        return f"{tag} {status} {message}"

    @staticmethod
    def build_list_response() -> str:
        return '* LIST (\\HasNoChildren) "/" "INBOX"'

    @staticmethod
    def build_fetch_response(sequence: int, body: str) -> list[str]:
        return [
            f"* {sequence} FETCH (BODY[TEXT] {{{len(body)}}}",
            body,
            ")",
        ]
