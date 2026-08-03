from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class LayoutMetrics:
    outer_margin: int
    spacing: int
    rates_height: int
    status_height: int
    side_width: int
    card_padding: int
    title_size: int
    body_size: int
    value_size: int

def metrics_for_width(width: int) -> LayoutMetrics:
    if width >= 1800:
        return LayoutMetrics(18, 16, 58, 34, 430, 20, 18, 20, 56)
    if width >= 1200:
        return LayoutMetrics(14, 12, 48, 30, 340, 16, 15, 16, 46)
    return LayoutMetrics(10, 8, 40, 26, 280, 12, 13, 14, 38)