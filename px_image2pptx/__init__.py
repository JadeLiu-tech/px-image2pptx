"""px-image2pptx -- Convert static images to editable PowerPoint slides.

Pipeline: image → OCR → textmask → mask-clip → inpaint → PPTX assembly.

OCR detects text regions. Textmask detects text ink pixels. Mask-clip ANDs
them so only OCR-confirmed text is masked. LAMA inpaints the masked regions.
PPTX assembly places editable text boxes over the clean background.

Quick start::

    from px_image2pptx import image_to_pptx
    image_to_pptx("slide.png", "output.pptx")

Or from the command line::

    px-image2pptx slide.png -o output.pptx
"""

__version__ = "0.1.0"

from px_image2pptx.pipeline import image_to_pptx

__all__ = ["image_to_pptx"]
