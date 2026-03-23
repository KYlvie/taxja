"""Helpers for repairing mojibake in legacy localized strings."""

from __future__ import annotations

from typing import Optional

CP1252_BYTE_BY_CODEPOINT = {
    0x20AC: 0x80,
    0x201A: 0x82,
    0x0192: 0x83,
    0x201E: 0x84,
    0x2026: 0x85,
    0x2020: 0x86,
    0x2021: 0x87,
    0x02C6: 0x88,
    0x2030: 0x89,
    0x0160: 0x8A,
    0x2039: 0x8B,
    0x0152: 0x8C,
    0x017D: 0x8E,
    0x2018: 0x91,
    0x2019: 0x92,
    0x201C: 0x93,
    0x201D: 0x94,
    0x2022: 0x95,
    0x2013: 0x96,
    0x2014: 0x97,
    0x02DC: 0x98,
    0x2122: 0x99,
    0x0161: 0x9A,
    0x203A: 0x9B,
    0x0153: 0x9C,
    0x017E: 0x9E,
    0x0178: 0x9F,
}

CP1252_CONTROL_REPLACEMENTS = {
    0x80: "\u20ac",
    0x82: "\u201a",
    0x83: "\u0192",
    0x84: "\u201e",
    0x85: "\u2026",
    0x86: "\u2020",
    0x87: "\u2021",
    0x88: "\u02c6",
    0x89: "\u2030",
    0x8A: "\u0160",
    0x8B: "\u2039",
    0x8C: "\u0152",
    0x8E: "\u017D",
    0x91: "\u2018",
    0x92: "\u2019",
    0x93: "\u201C",
    0x94: "\u201D",
    0x95: "\u2022",
    0x96: "\u2013",
    0x97: "\u2014",
    0x98: "\u02DC",
    0x99: "\u2122",
    0x9A: "\u0161",
    0x9B: "\u203A",
    0x9C: "\u0153",
    0x9E: "\u017E",
    0x9F: "\u0178",
}

MOJIBAKE_HINTS = (
    "\u00c3",
    "\u00c2",
    "\u00e2",
    "\u00d0",
    "\u00d1",
    "\u00c5",
    "\u00c4",
    "\u00e6",
    "\u00e7",
    "\u00e9\u203a",
    "\u00ef\u00bc",
    "\u00e5",
)


def _encode_windows_1252(text: str) -> Optional[bytes]:
    encoded = bytearray()

    for char in text:
        codepoint = ord(char)
        if codepoint <= 0xFF:
            encoded.append(codepoint)
            continue

        mapped = CP1252_BYTE_BY_CODEPOINT.get(codepoint)
        if mapped is None:
            return None

        encoded.append(mapped)

    return bytes(encoded)


def _replace_control_chars(text: str) -> str:
    return "".join(CP1252_CONTROL_REPLACEMENTS.get(ord(char), char) for char in text)


def repair_mojibake(text: str) -> str:
    """Repair common mojibake patterns created by cp1252/utf-8 mixups."""

    repaired = text

    for _ in range(2):
        has_control_chars = any(0x80 <= ord(char) <= 0x9F for char in repaired)
        looks_like_mojibake = any(marker in repaired for marker in MOJIBAKE_HINTS)

        if not has_control_chars and not looks_like_mojibake:
            break

        encoded = _encode_windows_1252(repaired)
        if encoded is None:
            break

        try:
            decoded = encoded.decode("utf-8")
        except UnicodeDecodeError:
            break

        if decoded == repaired:
            break

        repaired = decoded

    return _replace_control_chars(repaired)
