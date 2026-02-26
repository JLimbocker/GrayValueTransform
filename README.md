# GrayValueTransform

Streamlit app to transform grayscale `fill`, `stroke`, and SVG gradient `stop-color` values using a two-column CSV mapping.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Behavior

- CSV accepts two columns (`input`, `output`) in `0-255`, with optional header.
- Duplicate input values are allowed only if they map to the same output.
- Piecewise-linear interpolation is used between CSV points.
- Any encountered grayscale value outside the CSV input range raises an error.
- Only true grayscale colors are mapped (`R=G=B`) in `#RGB`, `#RRGGBB`, or `rgb(r,g,b)` forms.
- Existing `fill`, `stroke`, and `stop-color` values are updated (including inside `style` attributes).
- Geometry is preserved because only paint values are rewritten.
