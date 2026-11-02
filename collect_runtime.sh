#!/usr/bin/env bash
# Collect UxPlay + all its DLLs and GStreamer plugins into a self-contained
# runtime/ folder, so the app can run without MSYS2 installed.
#
# RUN THIS IN THE "MSYS2 UCRT64" TERMINAL (not PowerShell), from the folder that
# holds this script:
#     bash collect_runtime.sh
set -uo pipefail   # note: no -e; we handle errors ourselves so a dep-less DLL
                   # doesn't abort the whole run.

UCRT=/ucrt64
OUT="$(pwd)/AirPlayMirror-portable/runtime"
BIN="$OUT/bin"
PLUGINS="$OUT/lib/gstreamer-1.0"
SRC_PLUGINS="$UCRT/lib/gstreamer-1.0"

echo "== Finding uxplay.exe =="
UX=""
for c in "$UCRT/bin/uxplay.exe" \
         "$(command -v uxplay 2>/dev/null || true)" \
         "$HOME/UxPlay/build/uxplay.exe"; do
    if [[ -n "$c" && -f "$c" ]]; then UX="$c"; break; fi
done
if [[ -z "$UX" ]]; then
    echo "ERROR: uxplay.exe not found. Build it first." >&2
    exit 1
fi
echo "   using: $UX"

mkdir -p "$BIN" "$PLUGINS"
cp -f "$UX" "$BIN/uxplay.exe"

# Copy every /ucrt64/bin DLL a binary depends on, following transitive deps.
# The `|| true` keeps a dependency-less DLL from aborting the run.
copy_deps() {
    local target="$1" dll base deps
    deps="$(ldd "$target" 2>/dev/null | grep -iF "$UCRT/bin" | awk '{print $3}' || true)"
    while IFS= read -r dll; do
        [[ -n "$dll" && -f "$dll" ]] || continue
        base="$(basename "$dll")"
        if [[ ! -f "$BIN/$base" ]]; then
            cp -f "$dll" "$BIN/$base"
            copy_deps "$BIN/$base"
        fi
    done <<< "$deps"
}

echo "== Collecting uxplay.exe dependencies =="
copy_deps "$BIN/uxplay.exe"
echo "   bin now has $(find "$BIN" -maxdepth 1 -type f | wc -l) files"

echo "== Collecting GStreamer plugins + their dependencies =="
if [[ ! -d "$SRC_PLUGINS" ]]; then
    echo "ERROR: GStreamer plugins not found at $SRC_PLUGINS" >&2
    echo "Install them: pacman -S mingw-w64-ucrt-x86_64-gst-plugins-{base,good,bad} mingw-w64-ucrt-x86_64-gst-libav" >&2
    exit 1
fi
shopt -s nullglob
n=0
for p in "$SRC_PLUGINS"/*.dll; do
    cp -f "$p" "$PLUGINS/"
    copy_deps "$p"
    n=$((n+1))
done
echo "   copied $n plugins"

echo "== Done =="
echo "Files in bin:  $(find "$BIN" -maxdepth 1 -type f | wc -l)"
echo "Plugins:       $(find "$PLUGINS" -maxdepth 1 -type f | wc -l)"
echo "Total size:    $(du -sh "$OUT" | awk '{print $1}')"
echo
echo "Next: run build_portable.ps1 in PowerShell."
