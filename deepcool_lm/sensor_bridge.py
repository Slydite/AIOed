"""
Sensor Bridge for DeepCool LM360.
Communicates with JZFSSensorBridgeServer via named pipe \\\\.\\pipe\\jzfs_sensor_bridge_v2
using DCS2 protocol, falling back seamlessly to psutil.
"""

import ctypes
from ctypes import wintypes
import json
import logging
import struct
import threading
import time
import zlib
import psutil

from deepcool_lm.fps_monitor import FpsMonitor
from deepcool_lm.gpu_power import AmdGpuPower

logger = logging.getLogger("deepcool_lm.sensor")

PIPE_NAME = r"\\.\pipe\jzfs_sensor_bridge_v2"
DCS2_HEADER_FMT = "<4sBBHIII"
DCS2_HEADER_SIZE = 20

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)


class SensorBridge:
    """Acquires real-time system metrics from JZFS sensor service or psutil."""

    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._pipe_handle = None
        self._connected_to_pipe = False
        self._amd_power = AmdGpuPower()
        self._fps = FpsMonitor()

        self._stats = {
            "cpu_temp": 45.0,
            "cpu_load": 10.0,
            "cpu_power": 35.0,
            "cpu_clock": 4200.0,
            "gpu_temp": 40.0,
            "gpu_load": 5.0,
            "gpu_power": 25.0,
            "gpu_clock": 500.0,
            "ram_load": 40.0,
            "ram_used_gb": 12.0,
            "ram_total_gb": 32.0,
            "disk_temp": 40.0,
            "source": "initializing",
            "timestamp": time.time()
        }

    def start(self):
        """Start the background sensor monitoring thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="SensorBridgeWorker")
        self._thread.start()
        self._fps.start()
        logger.info("Sensor bridge service thread started.")

    def stop(self):
        """Stop monitoring thread and disconnect pipe."""
        self._running = False
        self._fps.stop()
        self._close_pipe()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("Sensor bridge service thread stopped.")

    def get_stats(self) -> dict:
        """Return a thread-safe copy of the latest sensor data."""
        with self._lock:
            stats = dict(self._stats)
        stats.update(self._fps.get())
        return stats

    def get_metric(self, metric_id: str, temp_unit: str = "C") -> tuple[str, str, float]:
        """
        Helper returning (value_text, unit_text, normalized_percent_0_to_100).
        Makes all themes cleanly interchangeable!
        """
        s = self.get_stats()
        metric_id = metric_id.lower()

        if metric_id in ("cpu_temp", "cpu_temperature"):
            val_c = s.get("cpu_temp") or 0.0
            if temp_unit.upper() == "F":
                val_f = (val_c * 9.0 / 5.0) + 32.0
                return f"{int(round(val_f))}", "°F", max(0.0, min(100.0, val_c))
            return f"{int(round(val_c))}", "°C", max(0.0, min(100.0, val_c))

        elif metric_id in ("cpu_load", "cpu_usage", "cpu_percent"):
            val = s.get("cpu_load") or 0.0
            return f"{val:4.1f}", "%", max(0.0, min(100.0, val))

        elif metric_id in ("cpu_power", "cpu_watt"):
            val = s.get("cpu_power") or 0.0
            pct = (val / 150.0) * 100.0  # Normalized to 150W scale
            return f"{val:.1f}", "W", max(0.0, min(100.0, pct))

        elif metric_id in ("cpu_clock", "cpu_freq"):
            mhz = s.get("cpu_clock") or 0.0
            ghz = mhz / 1000.0
            pct = (ghz / 6.0) * 100.0
            return f"{ghz:.2f}", "GHz", max(0.0, min(100.0, pct))

        elif metric_id in ("gpu_temp", "gpu_temperature"):
            val_c = s.get("gpu_temp") or 0.0
            if temp_unit.upper() == "F":
                val_f = (val_c * 9.0 / 5.0) + 32.0
                return f"{int(round(val_f))}", "°F", max(0.0, min(100.0, val_c))
            return f"{int(round(val_c))}", "°C", max(0.0, min(100.0, val_c))

        elif metric_id in ("gpu_load", "gpu_usage", "gpu_percent"):
            val = s.get("gpu_load") or 0.0
            return f"{val:4.1f}", "%", max(0.0, min(100.0, val))

        elif metric_id in ("gpu_power", "gpu_watt"):
            val = s.get("gpu_power") or 0.0
            pct = (val / 300.0) * 100.0  # Normalized to 300W scale
            return f"{val:.1f}", "W", max(0.0, min(100.0, pct))

        elif metric_id in ("gpu_clock", "gpu_freq"):
            mhz = s.get("gpu_clock") or 0.0
            pct = (mhz / 3000.0) * 100.0
            return f"{int(mhz)}", "MHz", max(0.0, min(100.0, pct))

        elif metric_id in ("ram_load", "ram_usage", "ram_percent", "memory"):
            val = s.get("ram_load") or 0.0
            return f"{val:4.1f}", "%", max(0.0, min(100.0, val))

        elif metric_id in ("ram_used", "ram_used_gb"):
            val = s.get("ram_used_gb") or 0.0
            tot = s.get("ram_total_gb") or 32.0
            pct = (val / tot) * 100.0 if tot > 0 else 0.0
            return f"{val:.1f}", "GB", max(0.0, min(100.0, pct))

        elif metric_id in ("disk_temp", "disk_temperature"):
            val_c = s.get("disk_temp") or 0.0
            return f"{int(round(val_c))}", "°C", max(0.0, min(100.0, val_c))

        elif metric_id in ("fps", "fps_avg"):
            val = s.get("fps_avg") or 0.0
            return f"{val:.0f}", "FPS", max(0.0, min(100.0, val / 240.0 * 100.0))

        elif metric_id in ("fps_1pct", "fps_low"):
            val = s.get("fps_1pct") or 0.0
            return f"{val:.0f}", "FPS", max(0.0, min(100.0, val / 240.0 * 100.0))

        # Default fallback
        return "N/A", "", 0.0

    def _worker_loop(self):
        """Main loop that maintains pipe connection or polls psutil."""
        while self._running:
            if not self._connected_to_pipe:
                if self._try_connect_pipe():
                    logger.info("Connected to JZFS Sensor Bridge pipe successfully.")
                else:
                    self._poll_psutil()
                    time.sleep(1.0)
                    continue

            # Read from pipe
            try:
                msg = self._read_pipe_message()
                if msg:
                    self._process_dcs2_message(msg)
                else:
                    if not self._running:
                        break
                    # Pipe was closed or disconnected
                    logger.debug("JZFS Sensor Bridge pipe read returned None, reconnecting...")
                    self._close_pipe()
                    self._poll_psutil()
                    time.sleep(1.0)
            except Exception as e:
                if not self._running:
                    break
                logger.debug(f"Pipe read error: {e}")
                self._close_pipe()
                self._poll_psutil()
                time.sleep(1.0)

    def _try_connect_pipe(self) -> bool:
        """Attempt to open named pipe and perform DCS2 handshake."""
        self._close_pipe()
        h = kernel32.CreateFileW(
            PIPE_NAME,
            0x80000000 | 0x40000000,
            0,
            None,
            3,  # OPEN_EXISTING
            0,
            None
        )
        if h == -1 or h == 0 or h is None:
            return False

        self._pipe_handle = h

        try:
            # Step 1: Send HELLO
            hello_payload = {"op": "HELLO", "version": "2.0.0", "client": "deepcool_lm"}
            self._send_dcs2_packet(hello_payload, seq=1)
            resp = self._read_pipe_message()
            if not resp or not resp.get("ok"):
                logger.debug(f"Unexpected HELLO response: {resp}")
                self._close_pipe()
                return False

            # Step 2: Send SUBSCRIBE_SENSOR
            sub_payload = {}
            self._send_dcs2_packet(sub_payload, op="SUBSCRIBE_SENSOR", seq=2)
            sub_resp = self._read_pipe_message()
            if not sub_resp or not sub_resp.get("ok"):
                logger.debug(f"Unexpected SUBSCRIBE response: {sub_resp}")
                self._close_pipe()
                return False

            self._connected_to_pipe = True
            return True
        except Exception as e:
            logger.debug(f"Error during DCS2 handshake: {e}")
            self._close_pipe()
            return False

    def _send_dcs2_packet(self, payload_dict: dict, op: str = None, seq: int = 1):
        if op:
            payload_dict["op"] = op
        payload_bytes = json.dumps(payload_dict).encode("utf-8")
        crc = zlib.crc32(payload_bytes) & 0xFFFFFFFF
        hdr = struct.pack(
            DCS2_HEADER_FMT,
            b"DCS2",
            2,      # version
            1,      # kind = request
            0,      # flags
            len(payload_bytes),
            seq,
            crc
        )
        packet = hdr + payload_bytes
        written = wintypes.DWORD()
        res = kernel32.WriteFile(self._pipe_handle, packet, len(packet), ctypes.byref(written), None)
        if not res or written.value != len(packet):
            raise IOError(f"WriteFile failed: {ctypes.get_last_error()}")

    def _read_pipe_message(self) -> dict | None:
        if not self._pipe_handle or not self._running:
            return None

        # Read 20-byte header
        hdr_buf = ctypes.create_string_buffer(DCS2_HEADER_SIZE)
        read = wintypes.DWORD()
        res = kernel32.ReadFile(self._pipe_handle, hdr_buf, DCS2_HEADER_SIZE, ctypes.byref(read), None)
        if not res or read.value < DCS2_HEADER_SIZE:
            return None

        magic, ver, kind, flags, plen, seq, pcrc = struct.unpack_from(DCS2_HEADER_FMT, hdr_buf.raw, 0)
        if magic != b"DCS2" or plen > 10 * 1024 * 1024:
            return None

        # Read payload
        payload_buf = ctypes.create_string_buffer(plen)
        res = kernel32.ReadFile(self._pipe_handle, payload_buf, plen, ctypes.byref(read), None)
        if not res or read.value < plen:
            return None

        payload_bytes = payload_buf.raw[:plen]
        calc_crc = zlib.crc32(payload_bytes) & 0xFFFFFFFF
        if calc_crc != pcrc:
            logger.debug("DCS2 CRC32 mismatch on read")
            return None

        return json.loads(payload_bytes.decode("utf-8", errors="replace"))

    def _process_dcs2_message(self, msg: dict):
        body = msg.get("body")
        if not isinstance(body, dict):
            return

        # Build lower-cased lookup map for robustness
        lookup = {k.lower(): v for k, v in body.items()}

        def get_val(key_name, default_val):
            item = lookup.get(key_name.lower())
            if item and isinstance(item, dict) and "Value" in item:
                try:
                    return float(item["Value"])
                except (ValueError, TypeError):
                    pass
            return default_val

        with self._lock:
            self._stats["cpu_temp"] = get_val("cpu temperature", self._stats["cpu_temp"])
            self._stats["cpu_power"] = get_val("cpu power", self._stats["cpu_power"])
            self._stats["cpu_clock"] = get_val("cpu clock", self._stats["cpu_clock"])
            self._stats["cpu_load"] = get_val("cpu usage", self._stats["cpu_load"])

            # GPU
            self._stats["gpu_temp"] = get_val("gpu temperature", self._stats["gpu_temp"])
            # DeepCool's bridge reports unit "-" when it has no GPU power sensor (e.g. AMD cards)
            gpu_power_item = lookup.get("gpu power")
            if isinstance(gpu_power_item, dict) and gpu_power_item.get("Unit") not in ("-", "", None):
                self._stats["gpu_power"] = get_val("gpu power", self._stats["gpu_power"])
            else:
                amd_watts = self._amd_power.read()
                if amd_watts is not None:
                    self._stats["gpu_power"] = amd_watts
            self._stats["gpu_clock"] = get_val("gpu clock", get_val("core gpu clock", self._stats["gpu_clock"]))
            self._stats["gpu_load"] = get_val("gpu usage", self._stats["gpu_load"])

            # Disk
            self._stats["disk_temp"] = get_val("disk temperature", self._stats["disk_temp"])

            # Supplement RAM via psutil
            ram = psutil.virtual_memory()
            self._stats["ram_load"] = ram.percent
            self._stats["ram_used_gb"] = ram.used / (1024**3)
            self._stats["ram_total_gb"] = ram.total / (1024**3)

            self._stats["source"] = "jzfs_bridge"
            self._stats["timestamp"] = time.time()

    def _poll_psutil(self):
        """Fallback when JZFS sensor service is unavailable."""
        with self._lock:
            self._stats["cpu_load"] = psutil.cpu_percent(interval=None)
            freq = psutil.cpu_freq()
            if freq:
                self._stats["cpu_clock"] = freq.current
            ram = psutil.virtual_memory()
            self._stats["ram_load"] = ram.percent
            self._stats["ram_used_gb"] = ram.used / (1024**3)
            self._stats["ram_total_gb"] = ram.total / (1024**3)
            self._stats["source"] = "psutil"
            self._stats["timestamp"] = time.time()

    def _close_pipe(self):
        self._connected_to_pipe = False
        if self._pipe_handle:
            try:
                kernel32.CloseHandle(self._pipe_handle)
            except Exception:
                pass
            self._pipe_handle = None
