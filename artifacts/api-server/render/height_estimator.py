"""
HeightEstimator — pre-render block height estimation for geometry-first layout.

All values are in CSS pixels at 96 dpi. Content zone assumes US Letter page
(215.9 × 279.4 mm) with 20 mm margins, yielding ~920 px usable height.

Conservative policy: all estimates round up to the nearest 8 px and a 5%
safety margin is applied to the zone budget. Overflow is a hard error;
extra whitespace is acceptable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any


# ── Page geometry constants ────────────────────────────────────────────────────

PAGE_HEIGHT_PX: int = 1056        # US Letter @ 96 dpi (11 in × 96)
MARGIN_PX: int = 76               # 20 mm converted to px (20 * 96 / 25.4 ≈ 76)
ZONE_HEIGHT_PX: int = PAGE_HEIGHT_PX - (2 * MARGIN_PX)   # ~904 px
HEADER_FOOTER_PX: int = 48        # running header + page number footer
CONTENT_ZONE_PX: int = ZONE_HEIGHT_PX - HEADER_FOOTER_PX  # ~856 px
ZONE_SAFETY_MARGIN: float = 0.05  # 5 % safety reduction on content zone
EFFECTIVE_ZONE_PX: int = math.floor(CONTENT_ZONE_PX * (1 - ZONE_SAFETY_MARGIN))  # ~813 px

CHARS_PER_LINE: int = 72          # approximate characters per content-width line
LINE_HEIGHT_PX: int = 24          # px per text line
INTER_BLOCK_SPACING_PX: int = 16  # vertical gap between blocks
ROUNDING_UNIT: int = 8            # round all estimates up to nearest multiple


# ── Block type height constants ─────────────────────────────────────────────

class BlockType(str, Enum):
    H1 = "h1"
    H2 = "h2"
    H3 = "h3"
    PARAGRAPH = "paragraph"
    TABLE_HEADER_ROW = "table_header_row"
    TABLE_DATA_ROW = "table_data_row"
    TABLE_TOTAL_ROW = "table_total_row"
    WS_TEXT_INPUT = "ws_text_input"
    WS_YN_CIRCLE = "ws_yn_circle"
    WS_DATE_FIELD = "ws_date_field"
    CALLOUT = "callout"
    SECTION_DIVIDER = "section_divider"
    COVER_PAGE = "cover_page"
    INTER_BLOCK = "inter_block"


FIXED_HEIGHTS_PX: dict[BlockType, int] = {
    BlockType.H1:               72,
    BlockType.H2:               56,
    BlockType.H3:               44,
    BlockType.TABLE_HEADER_ROW: 40,
    BlockType.TABLE_DATA_ROW:   32,
    BlockType.TABLE_TOTAL_ROW:  36,
    BlockType.WS_TEXT_INPUT:    48,
    BlockType.WS_YN_CIRCLE:     36,
    BlockType.WS_DATE_FIELD:    36,
    BlockType.INTER_BLOCK:      16,
}

FULL_PAGE_TYPES: frozenset[BlockType] = frozenset({
    BlockType.SECTION_DIVIDER,
    BlockType.COVER_PAGE,
})


@dataclass
class HeightEstimate:
    block_type: str
    estimated_px: int
    is_full_page: bool = False
    breakdown: dict[str, Any] | None = None


def _round_up(px: int) -> int:
    """Round up to the nearest ROUNDING_UNIT multiple."""
    return math.ceil(px / ROUNDING_UNIT) * ROUNDING_UNIT


class HeightEstimator:
    """Estimate the rendered height of a content block before page assignment.

    Usage:
        estimator = HeightEstimator()
        estimate = estimator.estimate(BlockType.PARAGRAPH, char_count=320)
        estimate = estimator.estimate(BlockType.H2)
        estimate = estimator.estimate_table(header=True, row_count=8)
        estimate = estimator.estimate_callout(content_px=96)
    """

    def estimate(
        self,
        block_type: BlockType | str,
        *,
        char_count: int = 0,
        row_count: int = 0,
    ) -> HeightEstimate:
        """Return a HeightEstimate for a block.

        For PARAGRAPH blocks, pass char_count. For table row types, pass
        row_count. For fixed-height blocks, neither is required.
        """
        bt = BlockType(block_type) if isinstance(block_type, str) else block_type

        if bt in FULL_PAGE_TYPES:
            return HeightEstimate(
                block_type=bt.value,
                estimated_px=EFFECTIVE_ZONE_PX,
                is_full_page=True,
            )

        if bt == BlockType.PARAGRAPH:
            return self._estimate_paragraph(char_count)

        if bt in (
            BlockType.TABLE_HEADER_ROW,
            BlockType.TABLE_DATA_ROW,
            BlockType.TABLE_TOTAL_ROW,
            BlockType.WS_TEXT_INPUT,
            BlockType.WS_YN_CIRCLE,
            BlockType.WS_DATE_FIELD,
        ):
            count = max(row_count, 1)
            base = FIXED_HEIGHTS_PX[bt]
            return HeightEstimate(
                block_type=bt.value,
                estimated_px=_round_up(base * count),
                breakdown={"row_height_px": base, "row_count": count},
            )

        if bt in FIXED_HEIGHTS_PX:
            return HeightEstimate(
                block_type=bt.value,
                estimated_px=FIXED_HEIGHTS_PX[bt],
            )

        # Unknown type — use a conservative paragraph-sized fallback
        return HeightEstimate(block_type=bt.value, estimated_px=_round_up(64))

    def estimate_paragraph(self, char_count: int) -> HeightEstimate:
        return self._estimate_paragraph(char_count)

    def _estimate_paragraph(self, char_count: int) -> HeightEstimate:
        if char_count <= 0:
            return HeightEstimate(
                block_type=BlockType.PARAGRAPH.value,
                estimated_px=FIXED_HEIGHTS_PX.get(BlockType.H3, 44),
            )
        lines = math.ceil(char_count / CHARS_PER_LINE)
        raw_px = lines * LINE_HEIGHT_PX + INTER_BLOCK_SPACING_PX
        return HeightEstimate(
            block_type=BlockType.PARAGRAPH.value,
            estimated_px=_round_up(raw_px),
            breakdown={"char_count": char_count, "lines": lines, "line_height_px": LINE_HEIGHT_PX},
        )

    def estimate_table(
        self,
        *,
        header: bool = True,
        data_rows: int = 0,
        total_rows: int = 0,
    ) -> HeightEstimate:
        px = 0
        if header:
            px += FIXED_HEIGHTS_PX[BlockType.TABLE_HEADER_ROW]
        px += FIXED_HEIGHTS_PX[BlockType.TABLE_DATA_ROW] * data_rows
        px += FIXED_HEIGHTS_PX[BlockType.TABLE_TOTAL_ROW] * total_rows
        return HeightEstimate(
            block_type="table",
            estimated_px=_round_up(px),
            breakdown={
                "header": header,
                "data_rows": data_rows,
                "total_rows": total_rows,
            },
        )

    def estimate_callout(self, content_px: int) -> HeightEstimate:
        CALLOUT_PADDING_PX = 48
        return HeightEstimate(
            block_type=BlockType.CALLOUT.value,
            estimated_px=_round_up(content_px + CALLOUT_PADDING_PX),
            breakdown={"content_px": content_px, "padding_px": CALLOUT_PADDING_PX},
        )

    def estimate_worksheet(
        self,
        *,
        text_inputs: int = 0,
        yn_circles: int = 0,
        date_fields: int = 0,
        table_rows: int = 0,
        title_px: int = 56,
        instructions_chars: int = 0,
    ) -> HeightEstimate:
        px = title_px
        px += FIXED_HEIGHTS_PX[BlockType.WS_TEXT_INPUT] * text_inputs
        px += FIXED_HEIGHTS_PX[BlockType.WS_YN_CIRCLE] * yn_circles
        px += FIXED_HEIGHTS_PX[BlockType.WS_DATE_FIELD] * date_fields
        px += FIXED_HEIGHTS_PX[BlockType.TABLE_DATA_ROW] * table_rows
        if instructions_chars:
            px += self._estimate_paragraph(instructions_chars).estimated_px
        return HeightEstimate(
            block_type="worksheet",
            estimated_px=_round_up(px),
            breakdown={
                "text_inputs": text_inputs,
                "yn_circles": yn_circles,
                "date_fields": date_fields,
                "table_rows": table_rows,
            },
        )

    @staticmethod
    def effective_zone_px() -> int:
        """Return the usable content height per page after safety margin."""
        return EFFECTIVE_ZONE_PX
