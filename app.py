import base64

import streamlit as st
import streamlit.components.v1 as components

from transform import ValidationError, parse_mapping_csv, transform_svg


def render_svg_preview(svg_text: str, *, height: int = 420) -> None:
    svg_b64 = base64.b64encode(svg_text.encode("utf-8")).decode("ascii")
    components.html(
        f"""
        <div style=\"border:1px solid #d9d9d9; border-radius:0.5rem; padding:0.5rem; background:#fff;\">
          <img
            alt=\"SVG preview\"
            src=\"data:image/svg+xml;base64,{svg_b64}\"
            style=\"max-width:100%; max-height:{height - 20}px; display:block; margin:auto;\"
          />
        </div>
        """,
        height=height,
    )


st.set_page_config(page_title="Gray Value Transform", layout="wide")
st.title("Gray Value Transform")
st.write("Upload an SVG and a two-column CSV (input, output) in the range 0-255.")

svg_file = st.file_uploader("SVG file", type=["svg"])
csv_file = st.file_uploader("CSV mapping file", type=["csv"])

if st.button("Process SVG", type="primary"):
    if not svg_file or not csv_file:
        st.error("Please upload both an SVG and a CSV file.")
    else:
        try:
            svg_text = svg_file.getvalue().decode("utf-8")
            csv_text = csv_file.getvalue().decode("utf-8")

            points = parse_mapping_csv(csv_text)
            transformed_svg, stats = transform_svg(svg_text, points)

            st.success("SVG transformed successfully.")
            st.write(
                {
                    "fills_changed": stats.fills_changed,
                    "strokes_changed": stats.strokes_changed,
                    "gradient_stop_colors_changed": stats.stop_colors_changed,
                    "interpolated_input_gray_values": sorted(stats.interpolated_inputs),
                }
            )

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Original SVG")
                render_svg_preview(svg_text)
            with col2:
                st.subheader("Transformed SVG")
                render_svg_preview(transformed_svg)

            st.download_button(
                "Download transformed SVG",
                data=transformed_svg.encode("utf-8"),
                file_name="transformed.svg",
                mime="image/svg+xml",
            )

        except ValidationError as exc:
            st.error(str(exc))
        except UnicodeDecodeError:
            st.error("Files must be UTF-8 encoded text.")
