"""End-to-end pipeline: image → editable PPTX.

Orchestrates: OCR → textmask → mask-clip → inpaint → PPTX assembly.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from px_image2pptx.assemble import assemble_pptx
from px_image2pptx.textmask import compute_masks


def image_to_pptx(
    image_path: str | Path,
    output_path: str | Path = "output.pptx",
    *,
    ocr_json: str | Path | None = None,
    lang: str = "auto",
    sensitivity: float = 16,
    dilation: int = 12,
    mask_padding: int = 15,
    min_font: int = 8,
    max_font: int = 72,
    skip_inpaint: bool = False,
    max_inpaint_size: int | None = None,
    work_dir: str | Path | None = None,
) -> dict:
    """Convert a static image to an editable PPTX.

    Args:
        image_path: Input image (PNG/JPG/WebP).
        output_path: Where to save the .pptx file.
        ocr_json: Pre-computed OCR JSON (skip OCR step if provided).
        lang: OCR language ("en", "ch", or "auto" to detect).
        sensitivity: Textmask sensitivity (lower = more aggressive).
        dilation: Textmask dilation in pixels.
        mask_padding: Padding around OCR bboxes for mask clipping.
        min_font: Minimum font size in points.
        max_font: Maximum font size in points.
        skip_inpaint: If True, skip inpainting (use original as background).
        max_inpaint_size: If set, downscale the longer edge to this many
            pixels before LAMA inpainting. Reduces time for large images.
        work_dir: Directory for intermediate files (default: temp dir).

    Returns:
        Report dict with pipeline statistics.
    """
    image_path = str(image_path)
    output_path = str(output_path)
    timings = {}

    # Work directory for intermediates (only created when explicitly requested)
    save_intermediates = work_dir is not None
    if save_intermediates:
        wdir = Path(work_dir)
        wdir.mkdir(parents=True, exist_ok=True)

    # Step 1: OCR
    t0 = time.time()
    if ocr_json:
        from px_image2pptx.ocr import load_ocr_json
        ocr_regions = load_ocr_json(ocr_json)
    else:
        from px_image2pptx.ocr import run_ocr, save_ocr_json

        # "ch" model handles both Chinese and English, so use it as default
        ocr_lang = "ch" if lang == "auto" else lang
        ocr_regions = run_ocr(image_path, lang=ocr_lang)

        if save_intermediates:
            save_ocr_json(ocr_regions, wdir / "text_regions.json")
    timings["ocr"] = round(time.time() - t0, 2)

    # Step 2: Textmask → clip to OCR → dilate
    t0 = time.time()
    image_bgr = cv2.imread(image_path)
    tight_mask, clipped_mask, dilated_mask = compute_masks(
        image_bgr, ocr_regions,
        sensitivity=sensitivity, dilation=dilation, padding=mask_padding,
    )
    if save_intermediates:
        Image.fromarray(tight_mask).save(str(wdir / "tight_mask.png"))
        Image.fromarray(clipped_mask).save(str(wdir / "clipped_mask.png"))
        Image.fromarray(dilated_mask).save(str(wdir / "mask.png"))
    timings["textmask"] = round(time.time() - t0, 2)

    # Step 3: Inpaint
    background_path = None
    _temp_bg = None
    if not skip_inpaint:
        t0 = time.time()
        from px_image2pptx.inpaint import inpaint

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        result = inpaint(image_rgb, dilated_mask, max_size=max_inpaint_size)

        if save_intermediates:
            bg_path = str(wdir / "background.png")
            Image.fromarray(result).save(bg_path)
            background_path = bg_path
        else:
            import tempfile
            _temp_bg = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            Image.fromarray(result).save(_temp_bg.name)
            background_path = _temp_bg.name
        timings["inpaint"] = round(time.time() - t0, 2)

    # Step 4: Assemble PPTX
    t0 = time.time()
    report = assemble_pptx(
        image_path=image_path,
        ocr_regions=ocr_regions,
        output_path=output_path,
        background_path=background_path,
        tight_mask=tight_mask,
        min_font=min_font,
        max_font=max_font,
    )
    timings["assemble"] = round(time.time() - t0, 2)

    # Clean up temp background file
    if _temp_bg is not None:
        import os
        os.unlink(_temp_bg.name)

    report["timings"] = timings
    if save_intermediates:
        report["work_dir"] = str(wdir)
        with open(wdir / "report.json", "w") as f:
            json.dump(report, f, indent=2)

    return report
