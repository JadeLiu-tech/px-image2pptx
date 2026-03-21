"""Text ink detection using classical computer vision.

Detects text pixels directly from image using adaptive thresholding,
connected component filtering, and Canny edge reinforcement. No ML model.

Returns both a tight mask (actual ink pixels, for color sampling) and a
dilated mask (for inpainting with safe coverage).
"""

from __future__ import annotations

import cv2
import numpy as np


def detect_text_ink(
    image: np.ndarray,
    block_size: int = 25,
    sensitivity: float = 16,
    max_component_pct: float = 2.0,
    min_component_area: int = 8,
    max_density: float = 0.9,
    max_density_area: int = 500,
    edge_neighborhood: int = 15,
    min_final_area: int = 10,
) -> np.ndarray:
    """Detect text ink pixels using adaptive thresholding and component analysis.

    Args:
        image: BGR numpy array (H, W, 3), uint8.
        block_size: Adaptive threshold block size (must be odd, >= 3).
        sensitivity: Adaptive threshold C parameter. Higher = less sensitive.
        max_component_pct: Max connected component area as % of image.
        min_component_area: Min component area in pixels (noise filter).
        max_density: Components with density above this AND area above
            max_density_area are treated as solid blobs.
        max_density_area: Minimum area for density filtering to apply.
        edge_neighborhood: Radius (px) for Canny edge reinforcement.
        min_final_area: Final cleanup — components smaller than this removed.

    Returns:
        Binary mask (H, W), uint8, 255 = text ink, 0 = background.
    """
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Ensure block_size is valid
    if block_size % 2 == 0:
        block_size += 1
    if block_size < 3:
        block_size = 3

    # Step 1: Dual thresholding (adaptive + Otsu intersection)
    adaptive = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
        blockSize=block_size, C=sensitivity,
    )
    _, otsu = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    )
    combined = cv2.bitwise_and(adaptive, otsu)

    # Step 2: Connect nearby stroke fragments
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    candidates = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel_close)

    # Step 3: Connected component filtering
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        candidates, connectivity=8,
    )
    max_area = h * w * (max_component_pct / 100.0)
    text_mask = np.zeros((h, w), dtype=np.uint8)

    for i in range(1, num_labels):
        x, y, cw, ch, area = stats[i]
        if area > max_area:
            continue
        if area < min_component_area:
            continue
        if cw > w * 0.3 and ch > h * 0.3:
            continue
        bbox_area = max(cw * ch, 1)
        density = area / bbox_area
        if density > max_density and area > max_density_area:
            continue
        text_mask[labels == i] = 255

    # Step 4: Canny edge reinforcement near detected text
    edges = cv2.Canny(gray, 80, 200)
    kernel_near = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (edge_neighborhood * 2 + 1, edge_neighborhood * 2 + 1),
    )
    text_neighborhood = cv2.dilate(text_mask, kernel_near)
    edge_near_text = cv2.bitwise_and(edges, text_neighborhood)
    text_mask = cv2.bitwise_or(text_mask, edge_near_text)

    # Step 5: Final cleanup
    kernel_fill = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    text_mask = cv2.morphologyEx(text_mask, cv2.MORPH_CLOSE, kernel_fill)

    num_labels2, labels2, stats2, _ = cv2.connectedComponentsWithStats(
        text_mask, connectivity=8,
    )
    clean_mask = np.zeros((h, w), dtype=np.uint8)
    for i in range(1, num_labels2):
        if stats2[i, cv2.CC_STAT_AREA] >= min_final_area:
            clean_mask[labels2 == i] = 255

    return clean_mask


def dilate_mask(mask: np.ndarray, dilation_px: int) -> np.ndarray:
    """Apply morphological dilation to a binary mask."""
    if dilation_px <= 0 or not np.any(mask):
        return mask.copy()
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (dilation_px * 2 + 1, dilation_px * 2 + 1),
    )
    return cv2.dilate(mask, kernel, iterations=1)


def clip_mask_to_ocr(
    mask: np.ndarray,
    ocr_regions: list[dict],
    padding: int = 15,
) -> np.ndarray:
    """Clip text mask to OCR-confirmed regions only.

    ANDs the textmask with rectangles from OCR bounding boxes so only
    pixels inside known text regions survive. Prevents masking illustrations,
    borders, and icons that textmask wrongly detects as text.
    """
    h, w = mask.shape[:2]
    ocr_mask = np.zeros_like(mask)

    for r in ocr_regions:
        b = r["bbox"]
        y1 = max(0, b["y1"] - padding)
        x1 = max(0, b["x1"] - padding)
        y2 = min(h, b["y2"] + padding)
        x2 = min(w, b["x2"] + padding)
        ocr_mask[y1:y2, x1:x2] = 255

    return np.minimum(mask, ocr_mask)


def compute_masks(
    image_bgr: np.ndarray,
    ocr_regions: list[dict],
    sensitivity: float = 16,
    dilation: int = 12,
    padding: int = 15,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Full textmask pipeline: detect → clip to OCR → dilate.

    Returns:
        (tight_mask, clipped_mask, dilated_mask)
        - tight_mask: raw ink pixels (for color sampling)
        - clipped_mask: tight mask AND-ed with OCR bboxes
        - dilated_mask: clipped + dilation (for inpainting)
    """
    tight = detect_text_ink(image_bgr, sensitivity=sensitivity)
    clipped = clip_mask_to_ocr(tight, ocr_regions, padding=padding)
    dilated = dilate_mask(clipped, dilation)
    return tight, clipped, dilated
