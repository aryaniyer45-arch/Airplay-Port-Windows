# AirPlay Receiver for Windows

Turn your Windows PC into an **AirPlay receiver** — mirror your iPhone/iPad screen,
or stream audio and see a **now‑playing screen** with album art and playback controls.
No account, no Apple software required.

![platform](https://img.shields.io/badge/platform-Windows%2010%2F11-blue)
![license](https://img.shields.io/badge/license-GPL--3.0-green)

> **Mirroring is one‑way:** you can *watch* the iPhone on your PC, not control it.
> (That's an Apple limitation — true on a Mac too.) Audio playback *can* be
> controlled, via the on‑screen play/pause/next buttons.

## Features

- 📱 **Screen mirroring** from iPhone/iPad over Wi‑Fi
- 🎵 **AirPlay audio** with a now‑playing screen — album art, title, artist, album
- ⏯️ **Media controls** — play / pause / next, sent back to your iPhone
- 🎛️ Low‑latency presets and GPU options
- 🪟 Clean, modern interface — no terminal windows
- 🔒 Runs locally; nothing leaves your network

## Download & install

Grab the latest from the **[Releases](../../releases)** page:

- **`AirPlayReceiver-Setup.exe`** — installer (recommended). Installs the app,
  sets up the firewall once, adds a shortcut. After that the app opens instantly.
- **`AirPlayMirror-portable.zip`** — no‑install version. Extract anywhere and run
  `AirPlayMirror.exe`. The first launch asks once to allow firewall access.

Then on your iPhone: **Control Centre → Screen Mirroring** (or the AirPlay audio
icon) → pick your PC's name. Both devices must be on the **same Wi‑Fi**.

> Windows 10/11 only. Needs the Microsoft **Edge WebView2** runtime, which is
> already on virtually all Windows 10/11 PCs.

## How it works

The interface is a small HTML/CSS app shown in a native window (via
[pywebview](https://pywebview.flowlib.com/)). The actual AirPlay engine is
**[UxPlay](https://github.com/FDH2/UxPlay)** plus **[GStreamer](https://gstreamer.freedesktop.org/)**,
which this app bundles and drives. Album art and track metadata come from UxPlay;
media control uses the DACP remote protocol.

## Building from source

Requires Windows, [MSYS2](https://www.msys2.org) (to build UxPlay) and Python 3.10+.

```powershell
# 1. In the "MSYS2 UCRT64" terminal — build UxPlay, then collect the engine:
#    (see UxPlay's Windows build guide first)
bash collect_runtime.sh

# 2. In PowerShell — bundle the app into a standalone exe + zip:
powershell -ExecutionPolicy Bypass -File .\build_portable.ps1

# 3. (optional) Make the installer with Inno Setup — open setup.iss, press F9.
```

To run it in development without building: `pip install -r requirements.txt`
then `python airplay_web.py`.

## License & credits

Licensed under **GPL‑3.0** (see [LICENSE](LICENSE)), because it builds on
GPL/LGPL components. Bundled third‑party software keeps its own licenses — see
the [`licenses/`](licenses/) folder:

- **UxPlay** — GPL‑3.0 · https://github.com/FDH2/UxPlay
- **GStreamer** and plugins — LGPL‑2.1 / GPL
- **gst‑libav / FFmpeg** — LGPL/GPL

This is an independent project and is not affiliated with Apple. "AirPlay" is a
trademark of Apple Inc., used here only to describe compatibility.
