"""Шаг 4: сегментация на логические блоки."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.parser import (
    TranscriptSegment,
    split_into_logical_chunks,
    parse_chunk,
    ParsedRecord,
)


@dataclass
class LogicalBlock:
    index: int
    text: str
    start: float | None
    end: float | None
    trigger: str | None = None

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "trigger": self.trigger,
        }


def _detect_trigger(text: str) -> str | None:
    lower = text.lower()
    markers = [
        ("далее", "marker:далее"),
        ("следующая запись", "marker:следующая_запись"),
        ("следующий перегон", "marker:следующий_перегон"),
        ("следующ", "marker:следующий"),
        ("перегон", "context:перегон"),
        ("километр", "context:км"),
        ("пикет", "context:пикет"),
        ("путь", "context:путь"),
        ("дефект", "context:дефект"),
        ("неисправност", "context:неисправность"),
    ]
    for token, label in markers:
        if token in lower:
            return label
    return None


def segment_logical_blocks(
    full_text: str,
    asr_segments: list[TranscriptSegment] | None = None,
) -> list[LogicalBlock]:
    chunks = split_into_logical_chunks(full_text, asr_segments)
    blocks: list[LogicalBlock] = []
    for idx, (text, start, end) in enumerate(chunks):
        blocks.append(LogicalBlock(
            index=idx,
            text=text,
            start=start,
            end=end,
            trigger=_detect_trigger(text),
        ))
    return blocks
