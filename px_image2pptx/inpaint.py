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


def inpaint(
    image: np.ndarray,
    mask: np.ndarray,
) -> np.ndarray:
    """Inpaint masked regions of an image using LAMA.

    Args:
        image: RGB numpy array (H, W, 3), uint8.
        mask: Grayscale numpy array (H, W), uint8. 255 = inpaint.

    Returns:
        Inpainted RGB numpy array (H, W, 3), uint8.
    """
    torch, download_model, LAMA_MODEL_URL, prepare_img_and_mask = _ensure_lama()

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

    pil_image = Image.fromarray(image)
    pil_mask = Image.fromarray(mask)
    img_t, mask_t = prepare_img_and_mask(pil_image, pil_mask, device)

    with torch.inference_mode():
        inpainted = model(img_t, mask_t)
        result = inpainted[0].permute(1, 2, 0).detach().cpu().numpy()
        result = np.clip(result * 255, 0, 255).astype(np.uint8)

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
