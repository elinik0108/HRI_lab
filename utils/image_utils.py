#!/usr/bin/env python
# =============================================================================
#                      HRI_lab_Pepper — Image Utilities
# =============================================================================
"""
Low-level helpers for converting Naoqi image frames to NumPy BGR arrays
suitable for OpenCV input.

Naoqi ``ALVideoDevice.getImageRemote`` returns a list:
    [width, height, layers, colorspace, timestamp_s, timestamp_us,
     binary_data, camera_id, fov_left_deg, fov_top_deg,
     fov_right_deg, fov_bottom_deg]

The binary_data element (index 6) is a bytes-like object.
"""

import numpy as np


# ── YUV422 (kYUV422ColorSpace = 9) → BGR ─────────────────────────────────────

def yuv422_to_bgr(data: bytes, width: int, height: int) -> np.ndarray:
    """
    Convert raw YUV422 (YUYV) bytes from Pepper's camera to a BGR uint8
    ndarray of shape ``(height, width, 3)``.

    Parameters
    ----------
    data : bytes
        Raw YUV422 buffer — length must equal ``width * height * 2``.
    width, height : int
        Image dimensions in pixels.

    Returns
    -------
    np.ndarray
        BGR image, dtype uint8, shape (H, W, 3).
    """
    yuv = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 2))

    # YUYV → separate planes
    y  = yuv[:, :, 0].astype(np.float32)
    u  = yuv[:, 0::2, 1].astype(np.float32)   # even columns
    v  = yuv[:, 1::2, 1].astype(np.float32)   # odd columns

    # Upsample U/V to full width
    u = np.repeat(u, 2, axis=1)[:, :width]
    v = np.repeat(v, 2, axis=1)[:, :width]

    # BT.601 YCbCr → RGB conversion
    u -= 128.0
    v -= 128.0

    r = np.clip(y + 1.402 * v,               0, 255)
    g = np.clip(y - 0.344136 * u - 0.714136 * v, 0, 255)
    b = np.clip(y + 1.772 * u,               0, 255)

    bgr = np.stack([b, g, r], axis=2).astype(np.uint8)
    return bgr


# ── Generic Naoqi frame → BGR ─────────────────────────────────────────────────

def naoqi_frame_to_numpy(al_image) -> np.ndarray:
    """
    Convert a Naoqi ``ALVideoDevice.getImageRemote`` return value to a BGR
    NumPy array.

    Supports colorspaces:
    * ``13`` — kBGRColorSpace  (3 channels, direct reshape)
    * ``11`` — kRGBColorSpace  (3 channels, R↔B swap)
    * ``9``  — kYUV422ColorSpace (2 bytes-per-pixel, YUYV)

    Parameters
    ----------
    al_image : list
        The 12-element list returned by ``ALVideoDevice.getImageRemote``.

    Returns
    -------
    np.ndarray
        BGR uint8 image of shape ``(height, width, 3)``.

    Raises
    ------
    ValueError
        If the colorspace is not supported.
    """
    width      = al_image[0]
    height     = al_image[1]
    colorspace = al_image[3]
    data       = bytes(al_image[6])

    if colorspace == 13:          # BGR (native, fastest path)
        frame = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))
        return frame.copy()

    if colorspace == 11:          # RGB → flip to BGR
        frame = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))
        return frame[:, :, ::-1].copy()

    if colorspace == 9:           # YUV422
        return yuv422_to_bgr(data, width, height)

    raise ValueError(
        f"Unsupported Naoqi colorspace {colorspace}. "
        "Use kBGRColorSpace (13), kRGBColorSpace (11), or kYUV422ColorSpace (9)."
    )
