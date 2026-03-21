"""End-to-end test for px-image2pptx.

Converts an example image to PPTX and verifies the output.

Run:
    pytest tests/test_e2e.py -v
"""

import os
import tempfile
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
SAMPLE_IMAGE = EXAMPLES_DIR / "chart_good1.png"


@pytest.fixture(autouse=True)
def _skip_model_check():
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"


def test_full_pipeline():
    """Full pipeline: OCR → textmask → inpaint → PPTX."""
    from px_image2pptx import image_to_pptx

    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "output.pptx"
        report = image_to_pptx(str(SAMPLE_IMAGE), str(out))

        assert out.exists(), "PPTX file was not created"
        assert out.stat().st_size > 0, "PPTX file is empty"
        assert report["ocr_regions"] > 0, "No OCR regions detected"
        assert report["text_boxes"] > 0, "No text boxes created"


def test_skip_inpaint():
    """Pipeline with --skip-inpaint (no LAMA model needed)."""
    from px_image2pptx import image_to_pptx

    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "output.pptx"
        report = image_to_pptx(str(SAMPLE_IMAGE), str(out), skip_inpaint=True)

        assert out.exists()
        assert report["background"] == "original"
        assert report["text_boxes"] > 0


def test_work_dir_saves_intermediates():
    """Intermediate files are saved only when work_dir is set."""
    from px_image2pptx import image_to_pptx

    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "output.pptx"
        work = Path(tmpdir) / "intermediates"
        image_to_pptx(str(SAMPLE_IMAGE), str(out), work_dir=str(work))

        assert (work / "text_regions.json").exists()
        assert (work / "tight_mask.png").exists()
        assert (work / "mask.png").exists()
        assert (work / "background.png").exists()
        assert (work / "report.json").exists()


def test_no_intermediates_by_default():
    """No intermediate files when work_dir is not set."""
    from px_image2pptx import image_to_pptx

    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "output.pptx"
        image_to_pptx(str(SAMPLE_IMAGE), str(out))

        # Only the output PPTX should exist
        files = list(Path(tmpdir).iterdir())
        assert files == [out]


def test_cli():
    """CLI produces a valid PPTX."""
    from px_image2pptx.cli import main

    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "output.pptx"
        main([str(SAMPLE_IMAGE), "-o", str(out)])

        assert out.exists()
        assert out.stat().st_size > 0
