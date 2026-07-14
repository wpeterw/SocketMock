from __future__ import annotations

from dataclasses import dataclass


@dataclass
class POP3Message:
    uid: int
    size: int
    body: str


class POP3Codec:
    @staticmethod
    def parse_command(line: str) -> tuple[str, str]:
        if not line:
            return "", ""
        parts = line.split(maxsplit=1)
        return parts[0].upper(), parts[1] if len(parts) > 1 else ""

    @staticmethod
    def build_ok(text: str) -> str:
        return f"+OK {text}"

    @staticmethod
    def build_err(text: str) -> str:
        return f"-ERR {text}"

    @staticmethod
    def build_stat(count: int, size: int) -> str:
        return f"+OK {count} {size}"

    @staticmethod
    def serialize_message(message: POP3Message) -> str:
        return message.body
