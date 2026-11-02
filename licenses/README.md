# Third-party licenses

This app bundles the following open-source components. Each keeps its own
license; this project as a whole is distributed under **GPL-3.0** (see the
`LICENSE` file in the repo root).

| Component | License | Source |
|-----------|---------|--------|
| **UxPlay** (the AirPlay engine) | GPL-3.0 | https://github.com/FDH2/UxPlay |
| **GStreamer** + base/good/bad plugins | LGPL-2.1 | https://gstreamer.freedesktop.org/ |
| **gst-libav / FFmpeg** | LGPL-2.1 / GPL-2.0+ | https://ffmpeg.org/ |
| **pywebview** | BSD-3-Clause | https://github.com/r0x0r/pywebview |
| **Pillow** | MIT-CMU (HPND) | https://github.com/python-imagelib/Pillow |
| **python-zeroconf** | LGPL-2.1 | https://github.com/python-zeroconf/python-zeroconf |

The full GPL-3.0 text is in the repo's `LICENSE` file (it also covers UxPlay,
which is GPL-3.0). The LGPL-2.1 text is available at
https://www.gnu.org/licenses/old-licenses/lgpl-2.1.txt

## When you distribute the built app

Because the binaries include GPL/LGPL components, keep this `licenses/` folder
alongside them in the release zip, and make the source available (this repo
does that). If you want to ship the exact license texts inside the zip too,
copy them from your MSYS2 install:

```
/ucrt64/share/licenses/
```

This is an independent project, not affiliated with Apple. "AirPlay" is a
trademark of Apple Inc., used only to describe compatibility.
