"""LAMA neural inpainting — reconstruct masked regions.

Requires the optional ``inpaint`` extra: ``pip install px-image2pptx[inpaint]``.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def _ensure_lama():
    """Import LAMA dependencies, raising a helpful error if not installed."""
    try:
        import torch
        from simple_lama_inpainting.models.model import (
            download_model, LAMA_MODEL_URL, prepare_img_and_mask,
        )
        return torch, download_model, LAMA_MODEL_URL, prepare_img_and_mask
    except ImportError:
        raise ImportError(
            "LAMA inpainting requires PyTorch and simple-lama-inpainting.\n"
            "Install with:\n  pip install px-image2pptx[inpaint]"
        ) from None


_cached_model = None
_cached_device = None


def _get_model():
    """Return the cached LAMA model, loading it on first call."""
    global _cached_model, _cached_device
    if _cached_model is not None:
        return _cached_model, _cached_device

    torch, download_model, LAMA_MODEL_URL, _ = _ensure_lama()

    if torch.backends.mps.is_available():
        device = torch.device("mps")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")

    model_path = download_model(LAMA_MODEL_URL)
    model = torch.jit.load(model_path, map_location=device)
    model.eval()
    model.to(device)

    _cached_model = model
    _cached_device = device
    return model, device


def inpaint(
    image: np.ndarray,
    mask: np.ndarray,
    max_size: int | None = None,
) -> np.ndarray:
    """Inpaint masked regions of an image using LAMA.

    Args:
        image: RGB numpy array (H, W, 3), uint8.
        mask: Grayscale numpy array (H, W), uint8. 255 = inpaint.
        max_size: If set, downscale the longer edge to this many pixels
            before LAMA inference, then upscale the result back.
            Reduces memory and compute for large images.

    Returns:
        Inpainted RGB numpy array (H, W, 3), uint8, same size as input.
    """
    _, _, _, prepare_img_and_mask = _ensure_lama()
    import torch

    model, device = _get_model()

    orig_h, orig_w = image.shape[:2]
    scaled = False

    if max_size and max(orig_h, orig_w) > max_size:
        scale = max_size / max(orig_h, orig_w)
        new_w = round(orig_w * scale)
        new_h = round(orig_h * scale)
        pil_image = Image.fromarray(image).resize((new_w, new_h), Image.LANCZOS)
        pil_mask = Image.fromarray(mask).resize((new_w, new_h), Image.NEAREST)
        scaled = True
    else:
        pil_image = Image.fromarray(image)
        pil_mask = Image.fromarray(mask)

    img_t, mask_t = prepare_img_and_mask(pil_image, pil_mask, device)

    with torch.inference_mode():
        inpainted = model(img_t, mask_t)
        result = inpainted[0].permute(1, 2, 0).detach().cpu().numpy()
        result = np.clip(result * 255, 0, 255).astype(np.uint8)

    if scaled:
        result = np.array(
            Image.fromarray(result).resize((orig_w, orig_h), Image.LANCZOS)
        )

    return result


def inpaint_file(
    image_path: str,
    mask_path: str,
    output_path: str,
) -> str:
    """Inpaint an image file with a mask file, save result.

    Returns the output path.
    """
    import cv2

    image = cv2.cvtColor(cv2.imread(image_path), cv2.COLOR_BGR2RGB)
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)

    result = inpaint(image, mask)

    result_bgr = cv2.cvtColor(result, cv2.COLOR_RGB2BGR)
    cv2.imwrite(output_path, result_bgr)
    return output_path
