"""
WinUSB Driver for DeepCool LM360 White Liquid Cooler LCD Display.
Device: USB\\VID_3633&PID_0026
Interface GUID: {13EB360B-BC1E-46CB-AC8B-EF3DA47B4062}
"""

import ctypes
from ctypes import wintypes
import logging
import time
import numpy as np

logger = logging.getLogger("deepcool_lm.usb")

VENDOR_ID = 0x3633
PRODUCT_ID = 0x0026
DEVICE_GUID = "{13EB360B-BC1E-46CB-AC8B-EF3DA47B4062}"
DEFAULT_DEVICE_PATH = rf"\\?\USB#VID_{VENDOR_ID:04X}&PID_{PRODUCT_ID:04X}#3690D8FE1974#{DEVICE_GUID}"

INIT_CMD = bytes([0xAA, 0x01, 0x00, 0x09, 0x29, 0x91])
REBOOT_CMD = bytes([0xAA, 0x01, 0x00, 0xEE, 0xE0, 0x1C])
FRAME_HEADER = bytes([0xAA, 0x08, 0x00, 0x00, 0x01, 0x00, 0x58, 0x02, 0x00, 0x2C, 0x01, 0xBC, 0x11])
SCREEN_OFF_CMD = bytes([0xAA, 0x04, 0x00, 0x03, 0x00, 0x00, 0x00, 0xDC, 0x9B])

BULK_OUT_ENDPOINT = 0x01
FRAME_SIZE = 320 * 240 * 2  # 153,600 bytes RGB565

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
winusb = ctypes.WinDLL('winusb', use_last_error=True)


def _build_rgb565_lut(percent: int) -> np.ndarray:
    """Precompute a 65536-element uint16 LUT for fast linear RGB565 brightness scaling (<0.2ms)."""
    alpha = max(0.0, min(1.0, percent / 100.0))
    vals = np.arange(65536, dtype=np.uint16)
    r = (vals >> 11) & 0x1F
    g = (vals >> 5) & 0x3F
    b = vals & 0x1F

    r_scaled = np.clip(np.round(r * alpha), 0, 31).astype(np.uint16)
    g_scaled = np.clip(np.round(g * alpha), 0, 63).astype(np.uint16)
    b_scaled = np.clip(np.round(b * alpha), 0, 31).astype(np.uint16)

    return (r_scaled << 11) | (g_scaled << 5) | b_scaled


class LM360UsbDriver:
    """Low-level driver communicating directly with LM360 via WinUSB."""

    def __init__(self, device_path: str = DEFAULT_DEVICE_PATH, initial_brightness: int = 100):
        self.device_path = device_path
        self.file_handle = None
        self.winusb_handle = None
        self.is_connected = False
        self._last_reconnect_attempt = 0.0

        # Handle legacy 1..5 scale if passed
        b_val = int(initial_brightness)
        if b_val <= 5:
            b_val = b_val * 20
        self.brightness_pct = max(0, min(100, b_val))
        self._lut = _build_rgb565_lut(self.brightness_pct) if self.brightness_pct < 100 else None

    @property
    def current_brightness(self) -> int:
        """Compatibility property returning percentage."""
        return self.brightness_pct

    def connect(self) -> bool:
        """Open device handle and initialize WinUSB."""
        if self.is_connected:
            return True

        self.close()

        h = kernel32.CreateFileW(
            self.device_path,
            0x80000000 | 0x40000000,
            1 | 2,
            None,
            3,
            0x80 | 0x40000000,
            None
        )

        if h == -1 or h == 0 or h is None:
            err = ctypes.get_last_error()
            logger.debug(f"CreateFileW failed for {self.device_path}: win32 err {err}")
            return False

        winusb_h = wintypes.HANDLE()
        if not winusb.WinUsb_Initialize(h, ctypes.byref(winusb_h)):
            err = ctypes.get_last_error()
            kernel32.CloseHandle(h)
            logger.debug(f"WinUsb_Initialize failed: win32 err {err}")
            return False

        self.file_handle = h
        self.winusb_handle = winusb_h
        self.is_connected = True

        try:
            # Send initialization handshake (opcode 0x09)
            self._write_pipe(INIT_CMD)
            time.sleep(0.05)
            logger.info("Successfully connected and initialized DeepCool LM360 WinUSB interface.")
            return True
        except Exception as e:
            logger.warning(f"Error during LM360 initialization write: {e}")
            self.close()
            return False

    def reboot(self) -> bool:
        """Send hardware reboot command (opcode 0xEE) to reset MCU and display registers."""
        if not self.ensure_connected():
            return False
        try:
            logger.info("Sending hardware REBOOT command (0xEE) to DeepCool LM360...")
            self._write_pipe(REBOOT_CMD)
            self.close()
            time.sleep(2.5)
            return self.connect()
        except Exception as e:
            logger.warning(f"Failed to reboot device: {e}")
            self.close()
            return False

    def _write_pipe(self, data: bytes) -> int:
        if not self.is_connected or not self.winusb_handle:
            raise IOError("Device not connected")

        buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        written = wintypes.ULONG()
        res = winusb.WinUsb_WritePipe(
            self.winusb_handle,
            BULK_OUT_ENDPOINT,
            buf,
            len(data),
            ctypes.byref(written),
            None
        )
        if not res:
            err = ctypes.get_last_error()
            self.is_connected = False
            raise IOError(f"WinUsb_WritePipe failed (win32 err {err})")
        return written.value

    def send_frame(self, frame_data: bytes) -> bool:
        """
        Send a 320x240 RGB565 framebuffer to the LCD.
        Hardware protocol requires FRAME_HEADER (13 bytes) as a separate USB transfer,
        followed by the raw pixel payload (153,600 bytes).
        Applies fast linear brightness LUT if brightness < 100%.
        """
        if len(frame_data) == 153613:
            pixel_bytes = frame_data[13:]
        elif len(frame_data) == FRAME_SIZE:
            pixel_bytes = frame_data
        else:
            raise ValueError(f"Invalid frame size: {len(frame_data)} (expected {FRAME_SIZE})")

        # Apply software linear brightness scaling
        if self.brightness_pct <= 0:
            pixel_bytes = bytes(FRAME_SIZE)
        elif self.brightness_pct < 100 and self._lut is not None:
            # Vectorized LUT lookup: takes ~0.16 ms
            pixel_u16 = np.frombuffer(pixel_bytes, dtype=np.uint16)
            pixel_bytes = self._lut[pixel_u16].tobytes()

        if not self.is_connected:
            now = time.time()
            if now - self._last_reconnect_attempt > 2.0:
                self._last_reconnect_attempt = now
                if not self.connect():
                    return False
            else:
                return False

        try:
            self._write_pipe(FRAME_HEADER)
            self._write_pipe(pixel_bytes)
            return True
        except Exception as e:
            logger.warning(f"Failed to send frame: {e}")
            self.close()
            return False

    def set_brightness(self, percent: int) -> bool:
        """Set brightness to percentage 0..100 (supports continuous linear adjustment)."""
        val = int(percent)
        # Migrate legacy 1..5 values
        if 1 <= val <= 5:
            val = val * 20
        target = max(0, min(100, val))

        self.brightness_pct = target
        if target < 100:
            self._lut = _build_rgb565_lut(target)
        else:
            self._lut = None

        logger.debug(f"Display brightness set to {target}%")
        return True

    def brightness_up(self, step: int = 10) -> int:
        """Increase brightness by step%."""
        self.set_brightness(min(100, self.brightness_pct + step))
        return self.brightness_pct

    def brightness_down(self, step: int = 10) -> int:
        """Decrease brightness by step%."""
        self.set_brightness(max(10, self.brightness_pct - step))
        return self.brightness_pct

    def screen_off(self) -> bool:
        """Turn display backlight/screen off."""
        if not self.ensure_connected():
            return False
        try:
            black_frame = bytes(FRAME_SIZE)
            self._write_pipe(FRAME_HEADER)
            self._write_pipe(black_frame)
            return True
        except Exception as e:
            logger.warning(f"Failed to turn screen off: {e}")
            self.close()
            return False

    def ensure_connected(self) -> bool:
        if self.is_connected:
            return True
        now = time.time()
        if now - self._last_reconnect_attempt > 2.0:
            self._last_reconnect_attempt = now
            return self.connect()
        return False

    def close(self):
        """Release WinUSB and file handles cleanly."""
        self.is_connected = False
        if self.winusb_handle:
            try:
                winusb.WinUsb_Free(self.winusb_handle)
            except Exception:
                pass
            self.winusb_handle = None

        if self.file_handle:
            try:
                kernel32.CloseHandle(self.file_handle)
            except Exception:
                pass
            self.file_handle = None
