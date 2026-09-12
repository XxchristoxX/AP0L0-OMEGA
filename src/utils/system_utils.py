# src/utils/system_utils.py
import platform
import subprocess
import threading
import time
import os
from pathlib import Path
try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

    class _PsutilFallback:
        """Métricas neutras para instalaciones mínimas o Android."""
        class _Memory:
            percent = 0.0
        class _Net:
            bytes_sent = 0
            bytes_recv = 0
        def cpu_percent(self, interval=None): return 0.0
        def virtual_memory(self): return self._Memory()
        def net_io_counters(self): return self._Net()
        def sensors_temperatures(self): return {}
    psutil = _PsutilFallback()
import math
import random
import sys
import ctypes

# ===== CONSTANTES DE SISTEMA =====
_ANDROID = bool(
    hasattr(sys, "getandroidapilevel")
    or os.environ.get("ANDROID_ROOT")
    or os.environ.get("TERMUX_VERSION")
)
_OS = "Android" if _ANDROID else platform.system()  # Windows, Darwin, Linux, Android
IS_WINDOWS = _OS == "Windows"
IS_LINUX = _OS == "Linux"
IS_MAC = _OS == "Darwin"
IS_ANDROID = _ANDROID

if IS_WINDOWS:
    _WIN_HIDE: dict = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    _WIN_HIDE: dict = {}

# ============================================================
# MÉTRICAS DEL SISTEMA (CPU, RAM, GPU, TEMP, NET)
# ============================================================
class _SysMetrics:
    def __init__(self):
        self.cpu = 0.0
        self.mem = 0.0
        self.net = 0.0
        self.gpu = -1.0
        self.tmp = -1.0
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        nc = psutil.net_io_counters()
        now = time.time()
        dt = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net = nc
        self._last_net_t = now
        gpu = self._get_gpu()
        tmp = self._get_temp()
        with self._lock:
            self.cpu = cpu
            self.mem = mem
            self.net = net
            self.gpu = gpu
            self.tmp = tmp

    def _get_gpu(self) -> float:
        try:
            import pynvml
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            return float(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)
        except Exception:
            pass
        if IS_WINDOWS:
            try:
                import ctypes
                lib = ctypes.WinDLL("nvml.dll")
                lib.nvmlInit_v2()
                dev = ctypes.c_void_p()
                lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev))
                class Util(ctypes.Structure):
                    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]
                u = Util()
                lib.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(u))
                return float(u.gpu)
            except Exception:
                pass
        if IS_LINUX:
            try:
                r = subprocess.run(
                    ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    vals = [float(v.strip()) for v in r.stdout.strip().split("\n") if v.strip()]
                    if vals:
                        return sum(vals) / len(vals)
            except Exception:
                pass
        return -1.0

    def _get_temp(self) -> float:
        try:
            temps = psutil.sensors_temperatures()
            for name in ["coretemp", "k10temp", "cpu_thermal", "acpitz", "cpu-thermal"]:
                if name in temps and temps[name]:
                    return temps[name][0].current
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass
        if IS_WINDOWS:
            try:
                import wmi
                w = wmi.WMI(namespace="root/wmi")
                tz = w.MSAcpi_ThermalZoneTemperature()
                if tz:
                    return (tz[0].CurrentTemperature / 10.0) - 273.15
            except Exception:
                pass
        if IS_LINUX:
            try:
                r = subprocess.run(["sensors"], capture_output=True, text=True, timeout=2)
                if r.returncode == 0:
                    for line in r.stdout.split("\n"):
                        if "°C" in line:
                            import re
                            match = re.search(r"([\d.]+)°C", line)
                            if match:
                                return float(match.group(1))
            except Exception:
                pass
        if IS_MAC:
            try:
                r = subprocess.run(["osx-cpu-temp"], capture_output=True, text=True, timeout=2)
                if r.returncode == 0:
                    return float(r.stdout.strip().replace("°C", ""))
            except Exception:
                pass
        return -1.0

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cpu": self.cpu,
                "mem": self.mem,
                "net": self.net,
                "gpu": self.gpu,
                "tmp": self.tmp,
            }

_metrics = _SysMetrics()

# ============================================================
# UTILIDADES DE ESCRITORIO Y ACCESOS DIRECTOS
# ============================================================
def _get_desktop_dir() -> Path:
    home = Path.home()
    if IS_WINDOWS:
        try:
            import ctypes
            from ctypes import wintypes
            class _GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD),
                            ("Data2", wintypes.WORD),
                            ("Data3", wintypes.WORD),
                            ("Data4", ctypes.c_ubyte * 8)]
            fid = _GUID(0xB4BFCC3A, 0xDB2C, 0x424C,
                        (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9,
                                             0x9A, 0x87, 0xC6, 0x41))
            buf = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None, ctypes.byref(buf)) == 0:
                p = Path(buf.value)
                ctypes.windll.ole32.CoTaskMemFree(buf)
                if p.is_dir():
                    return p
        except Exception:
            pass
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
                val, _ = winreg.QueryValueEx(key, "Desktop")
            p = Path(os.path.expandvars(val))
            if p.is_dir():
                return p
        except Exception:
            pass
    elif IS_LINUX:
        try:
            out = subprocess.run(["xdg-user-dir", "DESKTOP"],
                                 capture_output=True, text=True, timeout=5)
            p = Path(out.stdout.strip())
            if out.stdout.strip() and p != home and p.is_dir():
                return p
        except Exception:
            pass
        try:
            cfg = home / ".config" / "user-dirs.dirs"
            for line in cfg.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("XDG_DESKTOP_DIR"):
                    val = line.split("=", 1)[1].strip().strip('"')
                    p = Path(val.replace("$HOME", str(home)))
                    if p != home and p.is_dir():
                        return p
        except Exception:
            pass
    return home / "Desktop"

def _build_jarvis_icon(out_path: Path) -> bool:
    try:
        import PIL.Image, PIL.ImageDraw, PIL.ImageFilter
    except ImportError:
        return False

    CYAN = (0, 212, 255)
    DIM = (0, 100, 140)
    DARK = (0, 6, 10)
    GLOW = (0, 160, 200)
    WHITE = (220, 240, 255)

    def _render(sz: int) -> PIL.Image.Image:
        S = sz * 4
        img = PIL.Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = PIL.ImageDraw.Draw(img)
        cx = cy = S // 2
        R = S // 2 - 2

        d.ellipse([cx-R, cy-R, cx+R, cy+R], fill=(*DARK, 255))
        lw = max(2, S // 40)
        d.ellipse([cx-R, cy-R, cx+R, cy+R], outline=(*CYAN, 220), width=lw)

        R2 = int(R * 0.72)
        d.ellipse([cx-R2, cy-R2, cx+R2, cy+R2], outline=(*DIM, 180), width=max(1, lw // 2))

        R_inner = int(R * 0.30)
        R_outer = int(R * 0.62)
        spoke_w = max(1, S // 80)
        for i in range(6):
            angle = math.radians(i * 60 - 30)
            x1 = cx + int(R_inner * math.cos(angle))
            y1 = cy + int(R_inner * math.sin(angle))
            x2 = cx + int(R_outer * math.cos(angle))
            y2 = cy + int(R_outer * math.sin(angle))
            d.line([x1, y1, x2, y2], fill=(*GLOW, 200), width=spoke_w)

        for i in range(6):
            angle = math.radians(i * 60)
            for dr in range(lw * 2):
                rx = (R - lw - dr)
                d.point([cx + int(rx * math.cos(angle)),
                         cy + int(rx * math.sin(angle))],
                        fill=(*WHITE, 220))

        Ri = int(R * 0.26)
        d.ellipse([cx-Ri, cy-Ri, cx+Ri, cy+Ri], outline=(*CYAN, 255), width=max(2, lw))

        glow_layer = PIL.Image.new("RGBA", (S, S), (0, 0, 0, 0))
        gd = PIL.ImageDraw.Draw(glow_layer)
        Rc = int(R * 0.13)
        gd.ellipse([cx-Rc*2, cy-Rc*2, cx+Rc*2, cy+Rc*2], fill=(*CYAN, 110))
        glow_layer = glow_layer.filter(PIL.ImageFilter.GaussianBlur(S // 14))
        img = PIL.Image.alpha_composite(img, glow_layer)
        d = PIL.ImageDraw.Draw(img)
        d.ellipse([cx-Rc, cy-Rc, cx+Rc, cy+Rc], fill=(*WHITE, 255))
        return img.resize((sz, sz), PIL.Image.LANCZOS)

    try:
        sizes = [256, 128, 64, 48, 32, 16]
        frames = [_render(s) for s in sizes]
        frames[0].save(out_path, format="ICO", append_images=frames[1:],
                       sizes=[(s, s) for s in sizes])
        return True
    except Exception:
        return False

def _create_lnk_windows(lnk: str, target: str, args: str, work_dir: str, icon_loc: str) -> None:
    try:
        from win32com.client import Dispatch
        sh = Dispatch("WScript.Shell")
        sc = sh.CreateShortCut(lnk)
        sc.TargetPath = target
        sc.Arguments = f'"{args}"'
        sc.WorkingDirectory = work_dir
        sc.Description = "AP0L0 AI Assistant"
        sc.IconLocation = icon_loc
        sc.save()
        return
    except ImportError:
        pass

    vbs = "\n".join([
        'Set ws = CreateObject("WScript.Shell")',
        f'Set sc = ws.CreateShortcut("{lnk}")',
        f'sc.TargetPath = "{target}"',
        f'sc.Arguments = Chr(34) & "{args}" & Chr(34)',
        f'sc.WorkingDirectory = "{work_dir}"',
        'sc.Description = "AP0L0 AI Assistant"',
        f'sc.IconLocation = "{icon_loc}"',
        'sc.Save',
    ])
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".vbs")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(vbs)
        subprocess.Popen(["wscript.exe", "/nologo", tmp],
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
                         **(_WIN_HIDE if IS_WINDOWS else {})).wait(timeout=10)
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass
