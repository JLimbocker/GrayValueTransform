from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class TransformStats:
    fills_changed: int = 0
    strokes_changed: int = 0
    stop_colors_changed: int = 0
    interpolated_inputs: set[float] | None = None

    def __post_init__(self) -> None:
        if self.interpolated_inputs is None:
            self.interpolated_inputs = set()


HEX_COLOR_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
RGB_COLOR_RE = re.compile(
    r"^rgb\(\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*\)$",
    re.IGNORECASE,
)


class ValidationError(ValueError):
    pass


def _to_float(value: str, row_index: int, col_name: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValidationError(f"Row {row_index}: {col_name} value '{value}' is not numeric.") from exc
    if parsed < 0 or parsed > 255:
        raise ValidationError(f"Row {row_index}: {col_name} value {parsed} is outside 0-255.")
    return parsed


def parse_mapping_csv(csv_text: str) -> List[Tuple[float, float]]:
    reader = csv.reader(io.StringIO(csv_text))
    rows = [row for row in reader if row and any(cell.strip() for cell in row)]
    if not rows:
        raise ValidationError("CSV file is empty.")

    if any(len(row) != 2 for row in rows):
        raise ValidationError("Every CSV row must contain exactly 2 columns.")

    start_idx = 0
    first_two = [rows[0][0].strip(), rows[0][1].strip()]
    try:
        float(first_two[0])
        float(first_two[1])
    except ValueError:
        start_idx = 1

    points: List[Tuple[float, float]] = []
    input_to_output: Dict[float, float] = {}

    for i, row in enumerate(rows[start_idx:], start=start_idx + 1):
        inp = _to_float(row[0].strip(), i, "Input")
        out = _to_float(row[1].strip(), i, "Output")
        if inp in input_to_output and input_to_output[inp] != out:
            raise ValidationError(
                f"Input value {inp} appears multiple times with different outputs "
                f"({input_to_output[inp]} and {out})."
            )
        input_to_output[inp] = out
        points.append((inp, out))

    if len(points) < 2:
        raise ValidationError("CSV must contain at least two mapping rows.")

    points.sort(key=lambda p: p[0])
    return points


def map_gray(value: float, points: List[Tuple[float, float]], stats: TransformStats) -> float:
    min_x = points[0][0]
    max_x = points[-1][0]
    if value < min_x or value > max_x:
        raise ValidationError(
            f"Encountered grayscale value {value} outside mapping domain [{min_x}, {max_x}]."
        )

    for x, y in points:
        if value == x:
            return y

    stats.interpolated_inputs.add(value)

    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= value <= x1:
            t = (value - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)

    raise ValidationError(f"Could not interpolate value {value}.")


def parse_color_to_gray(color: str) -> Optional[int]:
    c = color.strip()
    if c in {"none", "currentColor"} or c.startswith("url("):
        return None

    hex_match = HEX_COLOR_RE.match(c)
    if hex_match:
        raw = hex_match.group(1)
        if len(raw) == 3:
            r = int(raw[0] * 2, 16)
            g = int(raw[1] * 2, 16)
            b = int(raw[2] * 2, 16)
        else:
            r = int(raw[0:2], 16)
            g = int(raw[2:4], 16)
            b = int(raw[4:6], 16)
        if r == g == b:
            return r
        return None

    rgb_match = RGB_COLOR_RE.match(c)
    if rgb_match:
        r, g, b = (int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3)))
        if any(v < 0 or v > 255 for v in (r, g, b)):
            return None
        if r == g == b:
            return r

    return None


def gray_to_hex(value: float) -> str:
    v = max(0, min(255, int(value + 0.5)))
    return f"#{v:02x}{v:02x}{v:02x}"


def transform_style(style: str, points: List[Tuple[float, float]], stats: TransformStats) -> str:
    parts = style.split(";")
    updated: List[str] = []
    for part in parts:
        if not part.strip() or ":" not in part:
            if part.strip():
                updated.append(part)
            continue
        key, value = part.split(":", 1)
        key_stripped = key.strip()
        value_stripped = value.strip()

        if key_stripped in {"fill", "stroke", "stop-color"}:
            gray = parse_color_to_gray(value_stripped)
            if gray is not None:
                mapped = map_gray(gray, points, stats)
                value_stripped = gray_to_hex(mapped)
                if key_stripped == "fill":
                    stats.fills_changed += 1
                elif key_stripped == "stroke":
                    stats.strokes_changed += 1
                else:
                    stats.stop_colors_changed += 1

        updated.append(f"{key_stripped}:{value_stripped}")
    return ";".join(updated)


def _transform_attr(elem: ET.Element, attr: str, points: List[Tuple[float, float]], stats: TransformStats) -> None:
    if attr not in elem.attrib:
        return
    gray = parse_color_to_gray(elem.attrib[attr])
    if gray is None:
        return
    mapped = map_gray(gray, points, stats)
    elem.attrib[attr] = gray_to_hex(mapped)
    if attr == "fill":
        stats.fills_changed += 1
    elif attr == "stroke":
        stats.strokes_changed += 1
    elif attr == "stop-color":
        stats.stop_colors_changed += 1


def transform_svg(svg_text: str, points: List[Tuple[float, float]]) -> Tuple[str, TransformStats]:
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise ValidationError(f"Invalid SVG XML: {exc}") from exc

    stats = TransformStats()
    for elem in root.iter():
        _transform_attr(elem, "fill", points, stats)
        _transform_attr(elem, "stroke", points, stats)
        _transform_attr(elem, "stop-color", points, stats)

        if "style" in elem.attrib:
            elem.attrib["style"] = transform_style(elem.attrib["style"], points, stats)

    transformed = ET.tostring(root, encoding="unicode")
    return transformed, stats
