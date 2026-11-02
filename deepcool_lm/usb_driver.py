"""
WinUSB Driver for DeepCool LM360 White Liquid Cooler LCD Display.
Device: USB\\VID_3633&PID_0026
Interface GUID: {13EB360B-BC1E-46CB-AC8B-EF3DA47B4062}
"""

import ctypes
from ctypes import wintypes
import logging
import threading
import time
import numpy as np

logger = logging.getLogger("deepcool_lm.usb")

VENDOR_ID = 0x3633
PRODUCT_ID = 0x0026
DEVICE_GUID = "{13EB360B-BC1E-46CB-AC8B-EF3DA47B4062}"
DEFAULT_DEVICE_PATH = rf"\\?\USB#VID_{VENDOR_ID:04X}&PID_{PRODUCT_ID:04X}#3690D8FE1974#{DEVICE_GUID}"

BULK_OUT_ENDPOINT = 0x01
FRAME_SIZE = 320 * 240 * 2  # 153,600 bytes RGB565

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
winusb = ctypes.WinDLL('winusb', use_last_error=True)


def _crc16_ccitt(data: bytes, init: int = 0x0000, poly: int = 0x1021) -> int:
    """CRC-16-CCITT checksum for DeepCool LM-Series (L122) microcontrollers."""
    crc = init
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def build_l122_packet(payload: bytes) -> bytes:
    """
    Construct an L122 framing packet:
      Byte 0:       0xAA (Sync byte)
      Bytes 1..2:   Payload length (Little-Endian uint16)
      Bytes 3..N:   Payload bytes
      Bytes N+1..N+2: CRC-16-CCITT of payload (Little-Endian uint16)
    """
    length = len(payload)
    pkt = bytearray([0xAA, length & 0xFF, (length >> 8) & 0xFF])
    pkt.extend(payload)
    crc = _crc16_ccitt(payload)
    pkt.append(crc & 0xFF)
    pkt.append((crc >> 8) & 0xFF)
    return bytes(pkt)


INIT_CMD = build_l122_packet(bytes([0x09]))                            # aa 01 00 09 29 91
REBOOT_CMD = build_l122_packet(bytes([0xEE]))                          # aa 01 00 ee e0 1c
FRAME_HEADER = bytes([0xAA, 0x08, 0x00, 0x00, 0x01, 0x00, 0x58, 0x02, 0x00, 0x2C, 0x01, 0xBC, 0x11])


def _build_rgb565_lut(percent: int) -> np.ndarray:
    """Precompute a 65536-element uint16 LUT for fast linear RGB565 brightness scaling (<0.1ms)."""
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

    def __init__(self, device_path: str = DEFAULT_DEVICE_PATH, initial_brightness: int = 100, orientation: int = 180):
        self.device_path = device_path
        self.file_handle = None
        self.winusb_handle = None
        self.is_connected = False
        self._last_reconnect_attempt = 0.0
        self._io_lock = threading.Lock()

        # Handle legacy 1..5 scale if passed
        b_val = int(initial_brightness)
        if 1 <= b_val <= 5:
            b_val = b_val * 20
        self.brightness_pct = max(0, min(100, b_val))
        self.orientation_deg = int(orientation)
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
            with self._io_lock:
                # Send initialization handshake (opcode 0x09)
                self._write_pipe_raw(INIT_CMD)
                time.sleep(0.04)
            logger.info("Successfully connected DeepCool LM360 WinUSB interface.")
            return True
        except Exception as e:
            logger.warning(f"Error during LM360 initialization write: {e}")
            self.close()
            return False

    def _write_pipe_raw(self, data: bytes) -> int:
        """Internal un-locked pipe write (caller must hold _io_lock)."""
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

    def reboot(self) -> bool:
        """Send hardware reboot command (opcode 0xEE) to reset MCU and display registers."""
        if not self.ensure_connected():
            return False
        try:
            logger.info("Sending hardware REBOOT command (0xEE) to DeepCool LM360...")
            with self._io_lock:
                self._write_pipe_raw(REBOOT_CMD)
            self.close()
            time.sleep(2.5)
            return self.connect()
        except Exception as e:
            logger.warning(f"Failed to reboot device: {e}")
            self.close()
            return False

    def send_frame(self, frame_data: bytes) -> bool:
        """
        Send a 320x240 RGB565 framebuffer to the LCD.
        Hardware protocol requires FRAME_HEADER (13 bytes) as a separate USB transfer,
        followed by the raw pixel payload (153,600 bytes).
        Applies fast linear RGB565 LUT scaling if brightness < 100%.
        """
        if len(frame_data) == 153613:
            pixel_bytes = frame_data[13:]
        elif len(frame_data) == FRAME_SIZE:
            pixel_bytes = frame_data
        else:
            raise ValueError(f"Invalid frame size: {len(frame_data)} (expected {FRAME_SIZE})")

        # Blank frame if brightness is 0
        if self.brightness_pct <= 0:
            pixel_bytes = bytes(FRAME_SIZE)
        elif self._lut is not None:
            # Fast vectorized LUT lookup (<0.1ms for full 320x240 frame)
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

        with self._io_lock:
            try:
                self._write_pipe_raw(FRAME_HEADER)
                self._write_pipe_raw(pixel_bytes)
                return True
            except Exception as e:
                logger.warning(f"Failed to send frame: {e}")
                self.close()
                return False

    def set_brightness(self, percent: int) -> bool:
        """Set display brightness percentage 0..100 with immediate vectorized software LUT scaling."""
        val = int(percent)
        # Migrate legacy 1..5 values
        if 1 <= val <= 5:
            val = val * 20
        target = max(0, min(100, val))

        self.brightness_pct = target
        self._lut = _build_rgb565_lut(target) if target < 100 else None

        logger.info(f"Display brightness set to {target}% (LUT active={self._lut is not None})")
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
        """Turn display backlight/screen off by sending blank black frame."""
        if not self.ensure_connected():
            return False
        with self._io_lock:
            try:
                black_frame = bytes(FRAME_SIZE)
                self._write_pipe_raw(FRAME_HEADER)
                self._write_pipe_raw(black_frame)
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
