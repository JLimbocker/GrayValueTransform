import pathlib
import unittest
import xml.etree.ElementTree as ET

from transform import parse_mapping_csv, transform_svg, ValidationError


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _paint_snapshot(svg_text: str):
    root = ET.fromstring(svg_text)
    values = []
    for elem in root.iter():
        for attr in ("fill", "stroke", "stop-color"):
            if attr in elem.attrib:
                values.append((elem.tag, attr, elem.attrib[attr]))
        if "style" in elem.attrib:
            parts = [p.strip() for p in elem.attrib["style"].split(";") if ":" in p]
            for part in parts:
                k, v = [s.strip() for s in part.split(":", 1)]
                if k in {"fill", "stroke", "stop-color"}:
                    values.append((elem.tag, f"style:{k}", v))
    return values


class TransformTests(unittest.TestCase):
    def test_reference_file_transforms_to_expected_paint_values(self):
        csv_text = (ROOT / "grayvalue_test_map.csv").read_text(encoding="utf-8")
        input_svg = (ROOT / "graytransform_ref_input.svg").read_text(encoding="utf-8")
        expected_svg = (ROOT / "graytransform_ref_output.svg").read_text(encoding="utf-8")

        points = parse_mapping_csv(csv_text)
        transformed, stats = transform_svg(input_svg, points)

        self.assertGreater(stats.fills_changed + stats.strokes_changed, 0)
        self.assertEqual(_paint_snapshot(transformed), _paint_snapshot(expected_svg))

    def test_duplicate_input_conflict_rejected(self):
        csv_text = "input,output\n10,20\n10,21\n"
        with self.assertRaises(ValidationError):
            parse_mapping_csv(csv_text)

    def test_reject_rows_with_not_exactly_two_columns(self):
        csv_text = "input,output,extra\n10,20,30\n"
        with self.assertRaises(ValidationError):
            parse_mapping_csv(csv_text)


if __name__ == "__main__":
    unittest.main()
