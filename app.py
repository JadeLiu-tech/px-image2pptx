"""Gradio demo for px-image2pptx — deploy on Hugging Face Spaces."""

import os
import tempfile
from pathlib import Path

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["FLAGS_enable_pir_api"] = "0"

import gradio as gr
from PIL import Image


def convert(image_path, lang):
    import traceback
    try:
        from px_image2pptx import image_to_pptx

        # Convert WebP to PNG if needed (PaddleOCR doesn't support WebP)
        img = Image.open(image_path)
        if img.format == "WEBP" or image_path.lower().endswith(".webp"):
            png_path = image_path.rsplit(".", 1)[0] + ".png"
            img.save(png_path)
            image_path = png_path

        tmpdir = tempfile.mkdtemp()
        out_pptx = os.path.join(tmpdir, "output.pptx")
        work_dir = os.path.join(tmpdir, "work")

        report = image_to_pptx(
            image_path,
            out_pptx,
            lang=lang,
            work_dir=work_dir,
        )

        # Load the inpainted background for preview
        bg_path = os.path.join(work_dir, "background.png")
        bg_preview = Image.open(bg_path) if os.path.exists(bg_path) else None

        summary = (
            f"**Text boxes:** {report['text_boxes']}  \n"
            f"**OCR regions:** {report['ocr_regions']}  \n"
            f"**Slide size:** {report['slide_size']['width_inches']}x"
            f"{report['slide_size']['height_inches']}\"  \n"
            f"**Timings:** {report.get('timings', {})}"
        )

        return bg_preview, out_pptx, summary
    except Exception as e:
        raise gr.Error(f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")


demo = gr.Interface(
    fn=convert,
    inputs=[
        gr.Image(type="filepath", label="Input image (slide, poster, infographic)"),
        gr.Radio(
            choices=["auto", "en", "ch"],
            value="auto",
            label="OCR language",
            info="auto = Chinese model (handles both Chinese & English)",
        ),
    ],
    outputs=[
        gr.Image(label="Inpainted background (text removed)"),
        gr.File(label="Download .pptx"),
        gr.Markdown(label="Report"),
    ],
    title="px-image2pptx",
    description=(
        "Convert a static image to an editable PowerPoint file. "
        "OCR detects text, classical CV builds a text mask, LAMA inpaints "
        "the background clean, and python-pptx reconstructs editable text boxes.\n\n"
        "For a full browser-based editor, visit [pxGenius.ai](https://pxgenius.ai)."
    ),
    examples=[
        ["examples/chart_good1.png", "auto"],
    ],
    cache_examples=False,
)

if __name__ == "__main__":
    demo.launch()
