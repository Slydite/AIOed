"""
AMD GPU board power via the driver's own atiadlxx.dll (ADL2 PMLog), no SDK required.
Used when DeepCool's sensor bridge has no GPU power sensor for the card (it reports unit "-").
"""

import ctypes
import logging

logger = logging.getLogger("deepcool_lm.gpu_power")

PMLOG_ASIC_POWER = 73  # board power in watts (observed ~47 W idle, ~300+ W under load on RX 9070 XT)
MAX_SENSORS = 256


class _Sensor(ctypes.Structure):
    _fields_ = [("supported", ctypes.c_int), ("value", ctypes.c_int)]


class _PMLogOutput(ctypes.Structure):
    _fields_ = [("size", ctypes.c_int), ("sensors", _Sensor * MAX_SENSORS)]


_ALLOC = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_int)


class AmdGpuPower:
    """Reads AMD GPU power in watts. read() returns None when unavailable."""

    def __init__(self):
        self._adl = None
        self._ctx = ctypes.c_void_p()
        self._adapters = 0
        self._buffers = []
        self._alloc_cb = _ALLOC(self._alloc)
        self._init_failed = False

    def _alloc(self, size: int) -> int:
        buf = ctypes.create_string_buffer(size)
        self._buffers.append(buf)
        return ctypes.addressof(buf)

    def _init(self) -> bool:
        if self._adl is not None:
            return True
        if self._init_failed:
            return False
        try:
            adl = ctypes.WinDLL("atiadlxx.dll")
            if adl.ADL2_Main_Control_Create(self._alloc_cb, 1, ctypes.byref(self._ctx)) != 0:
                raise OSError("ADL2_Main_Control_Create failed")
            count = ctypes.c_int()
            if adl.ADL2_Adapter_NumberOfAdapters_Get(self._ctx, ctypes.byref(count)) != 0 or count.value <= 0:
                raise OSError("no ADL adapters")
            self._adl = adl
            self._adapters = count.value
            return True
        except Exception as e:
            logger.info(f"AMD ADL GPU power unavailable: {e}")
            self._init_failed = True
            return False

    def read(self):
        """Highest board power across ADL adapters (the discrete GPU), in watts."""
        if not self._init():
            return None
        best = None
        out = _PMLogOutput()
        for idx in range(self._adapters):
            out.size = ctypes.sizeof(_PMLogOutput)
            try:
                if self._adl.ADL2_New_QueryPMLogData_Get(self._ctx, idx, ctypes.byref(out)) != 0:
                    continue
            except Exception:
                continue
            sensor = out.sensors[PMLOG_ASIC_POWER]
            if sensor.supported and (best is None or sensor.value > best):
                best = sensor.value
        return float(best) if best is not None else None
