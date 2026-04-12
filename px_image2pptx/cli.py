"""Command-line interface for px-image2pptx.

Usage::

    # Full pipeline (OCR + textmask + inpaint + PPTX)
    px-image2pptx slide.png -o output.pptx

    # With pre-computed OCR
    px-image2pptx slide.png -o output.pptx --ocr-json text_regions.json

    # Skip inpainting (solid background or use original)
    px-image2pptx slide.png -o output.pptx --skip-inpaint

    # Chinese slide
    px-image2pptx slide.png -o output.pptx --lang ch

    # Keep intermediate files
    px-image2pptx slide.png -o output.pptx --work-dir ./debug/
"""

from __future__ import annotations

import argparse
import sys
import time


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="px-image2pptx",
        description="Convert static images to editable PowerPoint slides.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  px-image2pptx slide.png -o output.pptx
  px-image2pptx slide.png -o output.pptx --lang ch
  px-image2pptx slide.png -o output.pptx --skip-inpaint
  px-image2pptx slide.png -o output.pptx --ocr-json ocr.json
  px-image2pptx slide.png -o output.pptx --work-dir ./debug/
""",
    )
    parser.add_argument("image", help="Input image (PNG/JPG/WebP)")
    parser.add_argument("-o", "--output", default="output.pptx",
                        help="Output PPTX path (default: output.pptx)")
    parser.add_argument("--ocr-json", default=None,
                        help="Pre-computed OCR JSON (skips OCR step)")
    parser.add_argument("--lang", default="auto", choices=["auto", "en", "ch"],
                        help="OCR language (default: auto-detect)")
    parser.add_argument("--sensitivity", type=float, default=16,
                        help="Textmask sensitivity (default: 16)")
    parser.add_argument("--dilation", type=int, default=12,
                        help="Textmask dilation pixels (default: 12)")
    parser.add_argument("--min-font", type=int, default=8,
                        help="Minimum font size in points (default: 8)")
    parser.add_argument("--max-font", type=int, default=72,
                        help="Maximum font size in points (default: 72)")
    parser.add_argument("--skip-inpaint", action="store_true",
                        help="Skip LAMA inpainting (use original or solid bg)")
    parser.add_argument("--max-inpaint-size", type=int, default=None,
                        help="Downscale longer edge to N px before inpainting "
                             "(e.g. 2048). Reduces time for large images.")
    parser.add_argument("--work-dir", default=None,
                        help="Directory for intermediate files")
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)

    from px_image2pptx.pipeline import image_to_pptx

    t0 = time.time()
    report = image_to_pptx(
        image_path=args.image,
        output_path=args.output,
        ocr_json=args.ocr_json,
        lang=args.lang,
        sensitivity=args.sensitivity,
        dilation=args.dilation,
        min_font=args.min_font,
        max_font=args.max_font,
        skip_inpaint=args.skip_inpaint,
        max_inpaint_size=args.max_inpaint_size,
        work_dir=args.work_dir,
    )
    elapsed = time.time() - t0

    print(f"Saved: {args.output}")
    print(f"  Text boxes: {report['text_boxes']}")
    print(f"  OCR regions: {report['ocr_regions']}")
    print(f"  Background: {report['background']}")
    print(f"  Slide: {report['slide_size']['width_inches']}x"
          f"{report['slide_size']['height_inches']}\"")
    print(f"  Time: {elapsed:.1f}s", end="")
    if "timings" in report:
        t = report["timings"]
        parts = [f"{k}={v}s" for k, v in t.items()]
        print(f" ({', '.join(parts)})")
    else:
        print()


if __name__ == "__main__":
    main()
