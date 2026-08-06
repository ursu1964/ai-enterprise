from __future__ import annotations

import re
from dataclasses import dataclass

from ai_enterprise.domain.hashing import hash_text
from ai_enterprise.domain.r4_interpretation import SourceSegment

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "api_key_assignment": re.compile(
        r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9_./+\-=]{8,}"
    ),
    "bearer_token": re.compile(r"(?i)bearer\s+[A-Za-z0-9_./+\-=]{12,}"),
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


@dataclass(frozen=True, slots=True)
class SourceRedactionResult:
    segments: tuple[SourceSegment, ...]
    indicators: tuple[str, ...]
    redacted: bool


def redact_source_segments(
    segments: tuple[SourceSegment, ...],
    *,
    enabled: bool,
) -> SourceRedactionResult:
    if not enabled:
        return SourceRedactionResult(segments=segments, indicators=(), redacted=False)
    indicators: list[str] = []
    redacted_segments: list[SourceSegment] = []
    for segment in segments:
        text = segment.text
        redacted_text = text
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(redacted_text):
                indicators.append(name)
                redacted_text = pattern.sub("[REDACTED_SECRET]", redacted_text)
        if redacted_text == text:
            redacted_segments.append(segment)
            continue
        redacted_segments.append(
            SourceSegment(
                id=segment.id,
                source_id=segment.source_id,
                sequence=segment.sequence,
                segment_type=segment.segment_type,
                heading_path=segment.heading_path,
                text=redacted_text,
                start_offset=segment.start_offset,
                end_offset=segment.start_offset + len(redacted_text),
                checksum=hash_text(redacted_text),
            )
        )
    return SourceRedactionResult(
        segments=tuple(redacted_segments),
        indicators=tuple(sorted(set(indicators))),
        redacted=bool(indicators),
    )


def contains_unredacted_secret(value: object) -> bool:
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in SECRET_PATTERNS.values())
    if isinstance(value, dict):
        return any(contains_unredacted_secret(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_unredacted_secret(item) for item in value)
    return False
