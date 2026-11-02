"""
Game FPS (average and 1% low) from PresentMon's ETW present stream.
Uses the console PresentMon that ships with the AMD driver (or Intel/NVIDIA FrameView builds);
nothing is downloaded. Reports the foreground app (falling back to the busiest presenter).
"""

import collections
import csv
import ctypes
import logging
import os
import subprocess
import threading
import time
from ctypes import wintypes

logger = logging.getLogger("deepcool_lm.fps")

SESSION_NAME = "AIOed_FPS"
WINDOW_SEC = 10.0         # rolling window for avg / 1% low
ACTIVE_SEC = 2.0          # a process counts as presenting if it drew a frame this recently
STALE_SEC = 30.0          # forget processes that stopped presenting
MIN_FRAMES = 60
IGNORED_APPS = {"dwm.exe", "explorer.exe", "searchhost.exe", "startmenuexperiencehost.exe"}  # shell/compositor

PRESENTMON_CANDIDATES = [
    r"C:\Program Files\AMD\CNext\CNext\PresentMon-x64.exe",
    r"C:\Program Files\PresentMon\PresentMon.exe",
    r"C:\Program Files\Intel\PresentMon\PresentMon.exe",
    r"C:\Program Files\NVIDIA Corporation\FrameView\bin\PresentMon_x64.exe",
    r"D:\Program Files\NVIDIA Corporation\FrameView\bin\PresentMon_x64.exe",
]

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)


def _foreground_pid() -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
    return pid.value


class _BasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in (
        "ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimits), ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _kill_on_close_job():
    """Job object that terminates PresentMon if this process dies, so no ETW session is orphaned."""
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = _ExtendedLimits()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        return None
    return job


def find_presentmon():
    for path in PRESENTMON_CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


class FpsMonitor:
    def __init__(self):
        self._path = find_presentmon()
        self._lock = threading.Lock()
        self._frames = {}  # pid -> deque[(wall_time, frame_ms, gpu_busy_ms)]
        self._names = {}
        self._proc = None
        self._job = None
        self._thread = None
        self._running = False

    def start(self):
        if self._running:
            return
        if not self._path:
            logger.info("PresentMon not found; FPS metrics disabled.")
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="FpsMonitor")
        self._thread.start()
        logger.info(f"FPS monitor started using {self._path}")

    def stop(self):
        self._running = False
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

    def _spawn(self):
        cmd = [self._path, "--output_stdout", "--no_console_stats", "--no_track_input",
               "--session_name", SESSION_NAME, "--stop_existing_session"]
        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
            text=True, bufsize=1, creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        self._job = self._job or _kill_on_close_job()
        if self._job:
            kernel32.AssignProcessToJobObject(self._job, wintypes.HANDLE(int(self._proc._handle)))

    def _run(self):
        while self._running:
            try:
                self._spawn()
                reader = csv.reader(self._proc.stdout)
                header = next(reader)
                col = {name: i for i, name in enumerate(header)}
                i_app, i_pid, i_ft = col["Application"], col["ProcessID"], col["FrameTime"]
                i_gpu = col.get("GPUBusy")
                for row in reader:
                    if not self._running:
                        break
                    try:
                        frame_ms = float(row[i_ft])
                        pid = int(row[i_pid])
                        gpu_ms = float(row[i_gpu]) if i_gpu is not None and row[i_gpu] != "NA" else 0.0
                    except (ValueError, IndexError):
                        continue
                    now = time.time()
                    with self._lock:
                        self._names[pid] = row[i_app]
                        q = self._frames.setdefault(pid, collections.deque())
                        q.append((now, frame_ms, gpu_ms))
                        while q and now - q[0][0] > WINDOW_SEC:
                            q.popleft()
            except Exception as e:
                logger.warning(f"PresentMon stream error: {e}")
            if self._running:
                time.sleep(3.0)  # restart if PresentMon exited unexpectedly

    def get(self) -> dict:
        """{'fps_avg', 'fps_1pct', 'fps_app'} for the active app; zeros/'' when nothing is presenting."""
        now = time.time()
        with self._lock:
            for pid in [p for p, q in self._frames.items() if not q or now - q[-1][0] > STALE_SEC]:
                del self._frames[pid]
                self._names.pop(pid, None)

            active = {
                pid: q for pid, q in self._frames.items()
                if self._names.get(pid, "").lower() not in IGNORED_APPS and now - q[-1][0] <= ACTIVE_SEC
            }
            best_pid = _foreground_pid()
            if best_pid not in active:
                best_pid = max(
                    active,
                    key=lambda pid: sum(f[2] for f in active[pid] if now - f[0] <= ACTIVE_SEC),
                    default=None,
                )

            frames = [f[1] for f in self._frames.get(best_pid, ()) if now - f[0] <= WINDOW_SEC and f[1] > 0]
            app = self._names.get(best_pid, "")

        if len(frames) < MIN_FRAMES:
            return {"fps_avg": 0.0, "fps_1pct": 0.0, "fps_app": ""}
        frames.sort()
        p99 = frames[min(len(frames) - 1, int(len(frames) * 0.99))]
        return {
            "fps_avg": 1000.0 * len(frames) / sum(frames),
            "fps_1pct": 1000.0 / p99,
            "fps_app": app,
        }
