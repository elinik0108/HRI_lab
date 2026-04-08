#!/usr/bin/env python
# =============================================================================
#                        HRI_lab_Pepper — Camera Module
# =============================================================================
"""
Streams frames from Pepper's camera as BGR NumPy arrays via a background
thread, using Naoqi ``ALVideoDevice``.

Usage
-----
    from HRI_lab_Pepper.session import PepperSession
    from HRI_lab_Pepper.vision.camera import PepperCamera

    session = PepperSession.connect("tcp://ROBOT_IP:9559")
    cam = PepperCamera(session)
    cam.start()

    frame = cam.get_frame()   # np.ndarray, shape (480, 640, 3), BGR
    cam.stop()
"""

import threading
import time
from collections import deque
from typing import Optional

import numpy as np

from HRI_lab_Pepper.config import (
    B, W, R,
    CAM_DEFAULT, CAM_RESOLUTION, CAM_COLORSPACE, CAM_FPS,
)
from HRI_lab_Pepper.utils.image_utils import naoqi_frame_to_numpy

_SUBSCRIBER_ID = "PepperAPI_Camera"
_RESOLUTION_LABELS = {
    0: "QQVGA 160x120",
    1: "QVGA 320x240",
    2: "VGA 640x480",
    3: "4VGA 1280x960",
}


class PepperCamera:
    """
    Background-threaded camera stream from Pepper.

    Parameters
    ----------
    session : qi.Session
        Active Naoqi session.
    camera_id : int
        ``0`` = top, ``1`` = bottom, ``2`` = stereo depth camera.
    resolution : int
        Naoqi resolution constant (``2`` = VGA 640×480).
    colorspace : int
        Naoqi colorspace constant (``13`` = BGR).
    fps : int
        Target frames per second (max ~15 over Wi-Fi for VGA).
    """

    def __init__(
        self,
        session: "qi.Session",
        camera_id: int = CAM_DEFAULT,
        resolution: int = CAM_RESOLUTION,
        colorspace: int = CAM_COLORSPACE,
        fps: int = CAM_FPS,
    ) -> None:
        self._video   = session.service("ALVideoDevice")
        self._cam_id  = camera_id
        self._res     = resolution
        self._cs      = colorspace
        self._fps     = fps
        self._handle  = None

        self._frame: Optional[np.ndarray] = None
        self._lock    = threading.Lock()
        self._frame_ready = threading.Condition(self._lock)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_seq = 0
        self._frame_ts = 0.0
        self._fps_samples = deque(maxlen=120)

        from HRI_lab_Pepper.session import PepperSession
        PepperSession.register_cleanup(self.stop)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Subscribe to ALVideoDevice and start the capture thread."""
        if self._running:
            return

        self._handle = self._video.subscribeCamera(
            _SUBSCRIBER_ID, self._cam_id, self._res, self._cs, self._fps
        )
        self._running = True
        self._thread  = threading.Thread(
            target=self._capture_loop, daemon=True, name="PepperCameraThread"
        )
        self._thread.start()
        print(f"{B}[Camera] Started — id={self._cam_id}, "
              f"res={self._res}, cs={self._cs}, fps={self._fps}{W}")

    def stop(self) -> None:
        """Stop the capture thread and unsubscribe from ALVideoDevice."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

        if self._handle is not None:
            try:
                self._video.unsubscribe(_SUBSCRIBER_ID)
            except Exception:
                pass
            self._handle = None
        print(f"{B}[Camera] Stopped.{W}")

    def __enter__(self) -> "PepperCamera":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Frame access
    # ------------------------------------------------------------------

    def get_frame(self) -> Optional[np.ndarray]:
        """
        Return the latest captured frame as a BGR NumPy array.

        Returns ``None`` if no frame has been captured yet.
        """
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def wait_for_frame(self, timeout: float = 5.0) -> Optional[np.ndarray]:
        """
        Block until a frame is available and return it.

        Parameters
        ----------
        timeout : float
            Maximum time to wait in seconds.

        Returns
        -------
        np.ndarray or None
            BGR frame, or ``None`` on timeout.
        """
        frame, _ = self.wait_for_next_frame(timeout=timeout)
        return frame

    def wait_for_next_frame(
        self,
        timeout: float = 5.0,
        after_seq: Optional[int] = None,
    ) -> tuple:
        """
        Block until a frame newer than *after_seq* is available.

        Returns the frame and its monotonically increasing sequence number.
        If *after_seq* is None, the latest available frame is returned.
        """
        deadline = time.time() + timeout
        with self._frame_ready:
            while True:
                if self._frame is not None and (
                    after_seq is None or self._frame_seq > after_seq
                ):
                    return self._frame.copy(), self._frame_seq

                remaining = deadline - time.time()
                if remaining <= 0:
                    return None, self._frame_seq

                self._frame_ready.wait(timeout=min(remaining, 0.1))

    def get_stats(self) -> dict:
        """Return live camera capture stats measured at the naoqi API layer."""
        with self._lock:
            if len(self._fps_samples) >= 2:
                span = self._fps_samples[-1] - self._fps_samples[0]
                actual_fps = (len(self._fps_samples) - 1) / span if span > 0 else 0.0
            else:
                actual_fps = 0.0

            frame_age_ms = max(0.0, (time.perf_counter() - self._frame_ts) * 1000.0) if self._frame_ts else 0.0

            return {
                "requested_fps": float(self._fps),
                "actual_fps": actual_fps,
                "frame_age_ms": frame_age_ms,
                "resolution": _RESOLUTION_LABELS.get(self._res, str(self._res)),
                "frame_seq": self._frame_seq,
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _capture_loop(self) -> None:
        while self._running:
            try:
                al_image = self._video.getImageRemote(self._handle)
                if al_image is not None:
                    frame = naoqi_frame_to_numpy(al_image)
                    self._video.releaseImage(self._handle)
                    now = time.perf_counter()
                    with self._frame_ready:
                        self._frame = frame
                        self._frame_seq += 1
                        self._frame_ts = now
                        self._fps_samples.append(now)
                        self._frame_ready.notify_all()
            except Exception as exc:
                print(f"{R}[Camera] Capture error: {exc}{W}")
                time.sleep(0.05)
