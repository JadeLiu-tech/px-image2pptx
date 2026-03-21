"""OCR text detection using PaddleOCR.

Detects text regions with bounding boxes, text content, and confidence scores.
Requires the optional ``ocr`` extra: ``pip install px-image2pptx[ocr]``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw


def _ensure_paddleocr():
    """Import PaddleOCR, raising a helpful error if not installed."""
    try:
        from paddleocr import PaddleOCR
        return PaddleOCR
    except ImportError:
        raise ImportError(
            "PaddleOCR is required for OCR. Install with:\n"
            "  pip install px-image2pptx[ocr]"
        ) from None


def run_ocr(image_path: str | Path, lang: str = "ch") -> list[dict]:
    """Run PaddleOCR on an image and return structured text regions.

    Args:
        image_path: Path to the input image.
        lang: OCR language (default "ch"). Use "en" for English only.

    Returns:
        List of text region dicts, each with:
        - id: int
        - text: str
        - confidence: float
        - bbox: {"x1": int, "y1": int, "x2": int, "y2": int}
    """
    import os
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

    PaddleOCR = _ensure_paddleocr()

    ocr = PaddleOCR(
        lang=lang,
        use_textline_orientation=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
    )
    results = list(ocr.predict(str(image_path)))

    regions = []
    idx = 0
    for page in results:
        polys = page.get("dt_polys", [])
        texts = page.get("rec_texts", [])
        scores = page.get("rec_scores", [])
        for poly, text, conf in zip(polys, texts, scores):
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            regions.append({
                "id": idx,
                "text": text,
                "confidence": round(float(conf), 4),
                "bbox": {
                    "x1": int(min(xs)),
                    "y1": int(min(ys)),
                    "x2": int(max(xs)),
                    "y2": int(max(ys)),
                },
            })
            idx += 1

    return regions


def save_ocr_json(regions: list[dict], path: str | Path) -> None:
    """Save OCR regions to JSON file."""
    with open(path, "w") as f:
        json.dump({"text_regions": regions}, f, indent=2, ensure_ascii=False)


def load_ocr_json(path: str | Path) -> list[dict]:
    """Load OCR regions from JSON file."""
    with open(path) as f:
        data = json.load(f)
    return data.get("text_regions", [])


def draw_ocr_overlay(image_path: str | Path, regions: list[dict]) -> Image.Image:
    """Draw OCR bounding boxes on image for visualization."""
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    for r in regions:
        b = r["bbox"]
        draw.rectangle([b["x1"], b["y1"], b["x2"], b["y2"]],
                        outline=(255, 50, 50), width=3)
        draw.rectangle([b["x1"], b["y1"], b["x2"], b["y2"]],
                        fill=(255, 50, 50, 40))
    return img
