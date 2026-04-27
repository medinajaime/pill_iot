"""
capture.py — Pi Camera v2 + NeoPixel LED ring control.

Triggers the camera after the trapdoor servo signals "closed", illuminates
the optical chamber, and returns a PIL Image for the preprocessing pipeline.
"""

import time
from PIL import Image
import numpy as np

# ── optional hardware imports ─────────────────────────────────────────────────

try:
    from picamera2 import Picamera2
    _PICAMERA_OK = True
except ImportError:
    _PICAMERA_OK = False

try:
    import board
    import neopixel as _neopixel
    _NEOPIXEL_OK = True
except ImportError:
    _NEOPIXEL_OK = False

# ── constants ─────────────────────────────────────────────────────────────────

# Pi Camera v2 native max is 3280×2464; 1920×1080 is faster and more than
# enough detail for a 35.6 mm bore at 53.9 mm working distance.
CAPTURE_RESOLUTION = (1920, 1080)

LED_COUNT      = 16    # NeoPixel ring LEDs
LED_GPIO_PIN   = 18    # BCM GPIO pin (WS2812 data)
LED_BRIGHTNESS = 0.8   # 0.0 – 1.0

# Time the camera exposure settles after LEDs come on.
SETTLE_DELAY_S = 0.30


class ChamberCamera:
    """
    Context-manager wrapper around Pi Camera v2 + NeoPixel LED ring.

    Usage::

        with ChamberCamera() as cam:
            img = cam.capture_pill()   # returns PIL Image
    """

    def __init__(
        self,
        resolution: tuple = CAPTURE_RESOLUTION,
        led_brightness: float = LED_BRIGHTNESS,
    ):
        self.resolution    = resolution
        self.led_brightness = led_brightness
        self._camera = None
        self._leds   = None

    # ── context manager ───────────────────────────────────────────────────────

    def __enter__(self):
        self._init_camera()
        self._init_leds()
        return self

    def __exit__(self, *_):
        self.close()

    # ── initialisation ────────────────────────────────────────────────────────

    def _init_camera(self):
        if not _PICAMERA_OK:
            return
        self._camera = Picamera2()
        cfg = self._camera.create_still_configuration(
            main={"size": self.resolution, "format": "RGB888"}
        )
        self._camera.configure(cfg)
        self._camera.start()
        time.sleep(0.5)  # sensor warm-up

    def _init_leds(self):
        if not _NEOPIXEL_OK:
            return
        pin = getattr(board, f"D{LED_GPIO_PIN}", None)
        if pin is None:
            return
        self._leds = _neopixel.NeoPixel(
            pin, LED_COUNT,
            brightness=self.led_brightness,
            auto_write=False,
            pixel_order=_neopixel.GRB,
        )

    # ── LED helpers ───────────────────────────────────────────────────────────

    def leds_on(self):
        if self._leds is None:
            return
        self._leds.fill((255, 255, 255))
        self._leds.show()

    def leds_off(self):
        if self._leds is None:
            return
        self._leds.fill((0, 0, 0))
        self._leds.show()

    # ── capture ───────────────────────────────────────────────────────────────

    def capture(self) -> Image.Image:
        """Grab one frame (LEDs must already be on)."""
        if self._camera is None:
            raise RuntimeError(
                "picamera2 not installed — cannot capture from hardware."
            )
        arr = self._camera.capture_array()
        return Image.fromarray(arr)

    def capture_pill(self, settle_delay: float = SETTLE_DELAY_S) -> Image.Image:
        """
        Full sequence: LEDs on → settle → capture → LEDs off.
        Call this after the trapdoor servo reports 'closed'.
        """
        self.leds_on()
        time.sleep(settle_delay)
        img = self.capture()
        self.leds_off()
        return img

    def close(self):
        self.leds_off()
        if self._camera is not None:
            self._camera.stop()
            self._camera.close()
            self._camera = None


# ── dev-machine stub ──────────────────────────────────────────────────────────

def load_image(path: str) -> Image.Image:
    """Drop-in for capture_pill() when running on a dev machine."""
    return Image.open(path).convert("RGB")
