"""
AirPlay Receiver - native window with a web UI (elegant + animated).
--------------------------------------------------------------------
Python runs the UxPlay engine exactly as before; the interface is HTML/CSS
rendered in a native window via pywebview (uses Edge WebView2 on Windows).

Dev preview:
    pip install pywebview pillow
    python airplay_web.py
"""

from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import webview  # pywebview

# --- engine discovery (same as the other builds) -------------------------
MSYS2_BIN_DIRS = [r"C:\msys64\ucrt64\bin", r"C:\msys64\mingw64\bin", r"C:\msys64\clangarm64\bin"]
BUILD_DIR_HINTS = [
    Path(os.path.expanduser("~")) / "UxPlay" / "build" / "uxplay.exe",
    Path(r"C:\msys64\home") / os.environ.get("USERNAME", "") / "UxPlay" / "build" / "uxplay.exe",
]
DEFAULT_NAME = "Windows PC"
CONFIG_DIR = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "AirPlayMirror"
CONFIG_FILE = CONFIG_DIR / "config.json"

PRESETS = {
    "Low latency (recommended)": ["-vsync", "no"],
    "Smooth 60 fps": ["-fps", "60"],
    "Best quality": [],
    "Low latency + low res": ["-vsync", "no", "-s", "1280x720"],
}
SINKS = {"d3d11 (safe)": ["-vs", "d3d11videosink"],
         "d3d12 (fastest)": ["-vs", "d3d12videosink"], "auto": []}
META_FIELDS = {"Title:": "title", "Artist:": "artist",
               "Album:": "album", "Album artist:": "album_artist"}


def parse_meta_line(line: str):
    for prefix, key in META_FIELDS.items():
        if line.startswith(prefix):
            return key, line[len(prefix):].strip()
    return None


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(sys.executable).parent
    return Path(__file__).resolve().parent


def engine_base_dir() -> Path:
    # where runtime/ lives (next to the exe when frozen)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def portable_uxplay():
    cand = engine_base_dir() / "runtime" / "bin" / "uxplay.exe"
    return cand if cand.is_file() else None


def find_uxplay(explicit=None):
    p = portable_uxplay()
    if p:
        return p
    cands = []
    if explicit:
        cands.append(Path(explicit))
    if os.environ.get("UXPLAY_PATH"):
        cands.append(Path(os.environ["UXPLAY_PATH"]))
    cands += [Path(d) / "uxplay.exe" for d in MSYS2_BIN_DIRS] + BUILD_DIR_HINTS
    for c in cands:
        try:
            if c.is_file():
                return c
        except OSError:
            pass
    from shutil import which
    found = which("uxplay")
    return Path(found) if found else None


def build_env(uxplay: Path) -> dict:
    env = os.environ.copy()
    extra = [str(uxplay.parent)] + [d for d in MSYS2_BIN_DIRS if os.path.isdir(d)]
    plugin_dir = uxplay.parent.parent / "lib" / "gstreamer-1.0"
    if plugin_dir.is_dir():
        env["GST_PLUGIN_SYSTEM_PATH_1_0"] = str(plugin_dir)
        env["GST_PLUGIN_PATH_1_0"] = str(plugin_dir)
    seen, parts = set(), []
    for p in extra + env.get("PATH", "").split(os.pathsep):
        if p and p not in seen:
            seen.add(p)
            parts.append(p)
    env["PATH"] = os.pathsep.join(parts)
    return env


_NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def uxplay_running() -> bool:
    if os.name != "nt":
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq uxplay.exe"],
                             capture_output=True, text=True, creationflags=_NOWIN).stdout
        return "uxplay.exe" in out.lower()
    except Exception:
        return False


def kill_stale_uxplay():
    """Clear any leftover uxplay.exe, then wait until it's really gone and let
    the OS release the network name - otherwise a fresh engine collides with the
    old one's mDNS registration and the PC vanishes from the AirPlay list."""
    if os.name != "nt":
        return
    try:
        subprocess.run(["taskkill", "/F", "/IM", "uxplay.exe"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=_NOWIN)
    except Exception:
        pass
    for _ in range(25):                 # up to ~5s: wait until it's actually gone
        if not uxplay_running():
            break
        time.sleep(0.2)
    time.sleep(1.0)                     # settle: let the mDNS name/socket free up


FIREWALL_RULE = "AirPlay Receiver (UxPlay)"


def _rule_exists(name: str) -> bool:
    """Query a firewall rule (no admin needed to read)."""
    try:
        r = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", f"name={name}"],
                           capture_output=True, text=True, creationflags=_NOWIN)
        return name.lower() in (r.stdout or "").lower()
    except Exception:
        return False


def ensure_firewall(uxplay_path: str):
    """Add an inbound-allow firewall rule for the engine, once, with a single
    admin prompt - so the PC is discoverable immediately instead of waiting on
    Windows' own (slow, easy-to-miss) firewall popup. Cached after it succeeds."""
    if os.name != "nt":
        return
    cfg = load_config()
    if cfg.get("firewall_ok"):
        return
    if _rule_exists(FIREWALL_RULE):
        cfg["firewall_ok"] = True
        save_config(cfg)
        return
    # Write the netsh command into a temp .bat so cmd handles the quoting of the
    # engine's path natively (long paths with spaces broke inline quoting), then
    # run that .bat elevated once.
    bat = Path(tempfile.gettempdir()) / "airplay_firewall.bat"
    try:
        bat.write_text(
            "@echo off\r\n"
            f'netsh advfirewall firewall add rule name="{FIREWALL_RULE}" '
            f'dir=in action=allow program="{uxplay_path}" enable=yes profile=private,domain\r\n',
            encoding="utf-8")
        ps = f"Start-Process -FilePath '{bat}' -Verb RunAs -WindowStyle Hidden -Wait"
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       creationflags=_NOWIN, timeout=120)
    except Exception:
        return
    finally:
        try:
            bat.unlink(missing_ok=True)
        except OSError:
            pass
    if _rule_exists(FIREWALL_RULE):     # only mark done if it really got added
        cfg["firewall_ok"] = True
        save_config(cfg)


def load_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        pass


class DacpController:
    """Sends play/pause/next commands back to the iPhone during AirPlay audio.

    UxPlay (-dacp) writes a file with two lines: the DACP id and the
    Active-Remote token. The iPhone advertises a control service over mDNS named
    iTunes_Ctrl_<dacp_id>._dacp._tcp; we resolve it and send an HTTP command
    with the Active-Remote header.
    """
    CMDS = {"playpause", "play", "pause", "nextitem", "previtem",
            "beginff", "beginrew", "volumeup", "volumedown"}

    def __init__(self, dacp_file: Path):
        self.f = dacp_file
        self._cache = None            # (dacp_id, ip, port) - reused after first lookup
        self._lock = threading.Lock()

    def _creds(self):
        try:
            lines = self.f.read_text().splitlines()
            if len(lines) >= 2:
                return lines[0].strip(), lines[1].strip()
        except OSError:
            pass
        return None, None

    def _resolve(self, dacp_id):
        """One brief mDNS lookup, with the responder opened AND closed right
        away so it never lingers alongside UxPlay's own advertising. Returns
        (ip, port) or None."""
        try:
            from zeroconf import Zeroconf
        except Exception:
            return None
        name = f"iTunes_Ctrl_{dacp_id}._dacp._tcp.local."
        zc = None
        try:
            zc = Zeroconf()
            info = zc.get_service_info("_dacp._tcp.local.", name, timeout=2000)
            if info and info.addresses:
                return (socket.inet_ntoa(info.addresses[0]), info.port)
        except Exception:
            pass
        finally:
            if zc is not None:
                try:
                    zc.close()
                except Exception:
                    pass
        return None

    def close(self):
        with self._lock:
            self._cache = None

    def send(self, cmd):
        if cmd not in self.CMDS:
            return {"ok": False, "error": "unknown command"}
        dacp_id, remote = self._creds()
        if not dacp_id or not remote:
            return {"ok": False, "error": "no active audio session"}
        with self._lock:
            cache = self._cache
        if cache and cache[0] == dacp_id:        # reuse - no mDNS, instant
            ip, port = cache[1], cache[2]
        else:                                    # first press: one brief lookup
            addr = self._resolve(dacp_id)
            if addr is None:
                return {"ok": False, "error": "iPhone remote not found"}
            ip, port = addr
            with self._lock:
                self._cache = (dacp_id, ip, port)
        url = f"http://{ip}:{port}/ctrl-int/1/{cmd}"
        try:
            req = urllib.request.Request(url, headers={"Active-Remote": remote})
            urllib.request.urlopen(req, timeout=2).read()
            return {"ok": True}
        except Exception as exc:
            with self._lock:                     # drop cache; re-lookup next press
                self._cache = None
            return {"ok": False, "error": str(exc)}


class Api:
    """Exposed to JavaScript as window.pywebview.api.*"""

    def __init__(self):
        self._proc = None
        self._tmp = Path(tempfile.mkdtemp(prefix="airplay_"))
        self._cover = self._tmp / "cover"
        self._dacp_file = self._tmp / "dacp.txt"
        self._dacp = DacpController(self._dacp_file)
        self._cover_mtime = 0.0
        self._meta = {}
        self._status = "idle"      # idle | ready | connected | playing
        self._log = []
        self._running_key = None   # (name, preset, sink, fullscreen) of the live engine
        self._running_name = None
        self.uxplay = find_uxplay(load_config().get("uxplay"))
        self.portable = self.uxplay is not None and portable_uxplay() is not None

    # ---- info ------------------------------------------------------------
    def config(self):
        cfg = load_config()
        return {
            "name": cfg.get("name", DEFAULT_NAME),
            "preset": cfg.get("preset", "Low latency (recommended)"),
            "sink": cfg.get("sink", "d3d11 (safe)"),
            "fullscreen": cfg.get("fullscreen", False),
            "presets": list(PRESETS), "sinks": list(SINKS),
            "engine_found": self.uxplay is not None,
            "portable": self.portable,
        }

    def state(self):
        running = self._proc is not None and self._proc.poll() is None
        if not running and self._status != "idle":
            self._status = "idle"
            self._meta = {}
        ts = 0.0
        try:
            if self._cover.is_file():
                ts = self._cover.stat().st_mtime
        except OSError:
            pass
        return {"running": running, "status": self._status,
                "meta": self._meta, "cover_ts": ts,
                "running_name": self._running_name if running else None}

    def cover(self):
        """Return the current album art as a data URL, or None."""
        try:
            if self._cover.is_file() and self._cover.stat().st_size > 200:
                data = self._cover.read_bytes()
                b64 = base64.b64encode(data).decode("ascii")
                # format sniff: JPEG starts FFD8, else assume PNG
                mime = "image/jpeg" if data[:2] == b"\xff\xd8" else "image/png"
                return f"data:{mime};base64,{b64}"
        except OSError:
            pass
        return None

    # ---- control ---------------------------------------------------------
    def start(self, opts):
        if self.uxplay is None or not self.uxplay.is_file():
            return {"ok": False, "error": "UxPlay engine not found."}
        name = (opts.get("name") or DEFAULT_NAME).strip() or DEFAULT_NAME
        key = (name, opts.get("preset"), opts.get("sink"), bool(opts.get("fullscreen")))
        # If the engine is already running with these exact settings, reuse it.
        # This is the key to no re-appear delay: we don't kill + relaunch (which
        # makes UxPlay's broadcast slow to recover) when nothing changed.
        if self._proc is not None and self._proc.poll() is None and key == self._running_key:
            return {"ok": True, "reused": True}
        # Otherwise (first start, or settings changed) launch a fresh engine.
        ensure_firewall(str(self.uxplay))   # one-time admin prompt, then remembered
        self._kill_engine()
        cfg = load_config()                 # merge, so we keep firewall_ok etc.
        cfg.update({"name": name, "preset": opts.get("preset"),
                    "sink": opts.get("sink"), "fullscreen": bool(opts.get("fullscreen"))})
        if not self.portable:
            cfg["uxplay"] = str(self.uxplay)
        save_config(cfg)
        kill_stale_uxplay()
        cmd = [str(self.uxplay), "-n", name, "-nh",
               "-ca", str(self._cover), "-dacp", str(self._dacp_file)]
        cmd += PRESETS.get(opts.get("preset"), [])
        cmd += SINKS.get(opts.get("sink"), ["-vs", "d3d11videosink"])
        if opts.get("fullscreen"):
            cmd.append("-fs")
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            self._proc = subprocess.Popen(cmd, env=build_env(self.uxplay),
                                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                          text=True, bufsize=1, creationflags=flags)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        self._running_key = key
        self._running_name = name
        self._status = "ready"
        threading.Thread(target=self._reader, daemon=True).start()
        return {"ok": True}

    def _kill_engine(self):
        proc, self._proc = self._proc, None
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        self._status = "idle"
        self._meta = {}
        self._running_key = None
        self._running_name = None
        self._dacp.close()          # drop the cached remote address
        try:
            self._cover.unlink(missing_ok=True)
        except OSError:
            pass

    def stop(self):
        """Fully turn the receiver off (used by 'Turn off' and on app close)."""
        self._kill_engine()
        return {"ok": True}

    def media(self, cmd):
        """play/pause/next/prev - sends a DACP command to the iPhone."""
        return self._dacp.send(cmd)

    def locate(self):
        res = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG, file_types=("uxplay (uxplay.exe)", "All files (*.*)"))
        if res:
            self.uxplay = Path(res[0])
            self.portable = portable_uxplay() is not None
            return {"ok": True, "path": str(self.uxplay)}
        return {"ok": False}

    # ---- internals -------------------------------------------------------
    def _reader(self):
        proc = self._proc
        if not proc or not proc.stdout:
            return
        for line in proc.stdout:
            line = line.rstrip("\n")
            self._log.append(line)
            if "Audio Metadata" in line:
                self._meta = {}
                self._status = "playing"
                continue
            kv = parse_meta_line(line)
            if kv:
                self._meta[kv[0]] = kv[1]
            elif "client" in line.lower() and "connect" in line.lower():
                if self._status in ("ready", "idle"):
                    self._status = "connected"


def main():
    base = app_base_dir()
    index = base / "web" / "index.html"
    api = Api()
    webview.create_window("AirPlay Receiver", url=str(index), js_api=api,
                          width=940, height=680, min_size=(820, 600),
                          background_color="#0b0b12")
    webview.start()
    api.stop()


if __name__ == "__main__":
    main()
