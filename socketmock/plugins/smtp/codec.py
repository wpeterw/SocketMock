from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SMTPMessage:
    from_addr: str
    recipients: list[str]
    headers: dict[str, str]
    body: str


class SMTPCodec:
    @staticmethod
    def parse_command(line: str) -> tuple[str, str]:
        if not line:
            return "", ""
        parts = line.split(" ", 1)
        return parts[0].upper(), parts[1] if len(parts) > 1 else ""

    @staticmethod
    def parse_mail_from(arg: str) -> str:
        return arg.split(":", 1)[1].strip("<>") if ":" in arg else arg.strip("<>")

    @staticmethod
    def parse_rcpt_to(arg: str) -> str:
        return arg.split(":", 1)[1].strip("<>") if ":" in arg else arg.strip("<>")

    @staticmethod
    def parse_message(lines: list[str]) -> SMTPMessage:
        headers: dict[str, str] = {}
        body_lines: list[str] = []
        in_headers = True
        for line in lines:
            if in_headers and not line:
                in_headers = False
                continue
            if in_headers:
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip()] = value.strip()
                else:
                    body_lines.append(line)
            else:
                body_lines.append(line)
        return SMTPMessage(
            from_addr=headers.get("From", ""),
            recipients=headers.get("To", "").split(",") if headers.get("To") else [],
            headers=headers,
            body="\n".join(body_lines).strip(),
        )

    @staticmethod
    def serialize_message(message: SMTPMessage) -> str:
        lines = [f"From: {message.from_addr}"]
        if message.recipients:
            lines.append(f"To: {', '.join(message.recipients)}")
        for key, value in message.headers.items():
            if key not in {"From", "To"}:
                lines.append(f"{key}: {value}")
        lines.append("")
        lines.append(message.body)
        return "\n".join(lines)

    @staticmethod
    def build_response(code: int, text: str) -> str:
        return f"{code} {text}"

    @staticmethod
    def build_banner(hostname: str) -> str:
        return f"220 {hostname} ESMTP ready"


class SMTPState(Any):
    pass
