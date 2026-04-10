#!/usr/bin/env python
# =============================================================================
#                    HRI_lab_Pepper — Tablet service
# =============================================================================
"""
Controls Pepper's chest tablet via Naoqi ``ALTabletService``.

Note: ``ALTabletService`` is marked deprecated in Naoqi 2.8 but remains
      functional on Pepper hardware.

Usage
-----
    from HRI_lab_Pepper.session import PepperSession
    from HRI_lab_Pepper.tablet import TabletService

    session = PepperSession.connect("tcp://ROBOT_IP:9559")
    tablet = TabletService(session)

    tablet.show_image("https://example.com/image.png")
    tablet.show_webview("http://192.168.1.100:8080/menu")
    tablet.set_brightness(0.8)
    tablet.hide()
"""

import time

from HRI_lab_Pepper.config import B, W, R


class TabletService:
    """
    Interface for Pepper's chest tablet.

    Parameters
    ----------
    session : qi.Session
        Active Naoqi session.
    """

    def __init__(self, session: "qi.Session") -> None:
        self._tablet = session.service("ALTabletService")
        try:
            self._tablet.enableWifi()
        except Exception:
            pass
        self._direct_mode = False   # set True once loadUrl proves unreliable
        print(f"{B}[Tablet] Ready.{W}")

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def show_image(self, url: str) -> None:
        """
        Display an image on the tablet.

        Parameters
        ----------
        url : str
            HTTP(S) URL or ``file://`` path accessible from the robot.
        """
        self._tablet.showImage(url)

    def show_webview(self, url: str, retries: int = 3, retry_delay: float = 0.6) -> bool:
        """
        Open a URL in the tablet's web view.

        Tries the two-step ``loadUrl`` + ``showWebview()`` approach first.
        If ``loadUrl`` returns False on all attempts (common on some firmware
        versions), it permanently switches to direct ``showWebview(url)`` mode
        for the rest of the session to avoid the retry delay on every call.
        """
        try:
            self._tablet.wakeUp()
            self._tablet.turnScreenOn(True)
        except Exception:
            pass

        if not self._direct_mode:
            for attempt in range(1, retries + 1):
                try:
                    self._tablet.cleanWebview()
                    ok = self._tablet.loadUrl(url)
                    if ok:
                        time.sleep(0.3)
                        self._tablet.showWebview()
                        print(f"{B}[Tablet] Page loaded (attempt {attempt}): {url}{W}")
                        return True
                    else:
                        print(f"[Tablet] loadUrl returned False on attempt {attempt}, retrying …")
                except Exception as exc:
                    print(f"[Tablet] Attempt {attempt} error: {exc}")
                if attempt < retries:
                    time.sleep(retry_delay)

            # loadUrl consistently fails on this firmware — switch to direct mode
            # permanently so future calls skip the retry loop entirely.
            print(f"[Tablet] loadUrl unreliable — switching to direct showWebview(url) mode.")
            self._direct_mode = True

        # Direct mode: single showWebview(url) call
        try:
            self._tablet.showWebview(url)
            print(f"{B}[Tablet] showWebview (direct): {url}{W}")
            return True
        except Exception as exc:
            print(f"[Tablet] {R}showWebview failed: {exc}{W}")
            return False

    def show_video(self, url: str) -> None:
        """
        Stream and display a video on the tablet.

        Parameters
        ----------
        url : str
            HTTP/RTSP video URL.
        """
        self._tablet.playVideo(url)

    def stop_video(self) -> None:
        """Stop any ongoing video playback."""
        self._tablet.stopVideo()

    def hide(self) -> None:
        """Hide the current tablet content (show black screen)."""
        self._tablet.hide()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_brightness(self, brightness: float) -> None:
        """
        Set tablet screen brightness.

        Parameters
        ----------
        brightness : float
            Value in [0.0, 1.0].
        """
        brightness = max(0.0, min(1.0, float(brightness)))
        self._tablet.setBrightness(brightness)

    def get_brightness(self) -> float:
        """Return current tablet brightness (0.0–1.0)."""
        return self._tablet.getBrightness()

    def enable_wifi(self, enabled: bool = True) -> None:
        """Enable or disable the tablet's Wi-Fi."""
        self._tablet.enableWifi() if enabled else self._tablet.disableWifi()

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def set_on_touch_callback(self, callback) -> None:
        """
        Register a callback called when the tablet is touched.

        Parameters
        ----------
        callback : callable
            ``callback(x: float, y: float)`` where ``x``, ``y`` are
            normalised touch coordinates [0, 1].
        """
        self._tablet.onTouchDown.connect(callback)
