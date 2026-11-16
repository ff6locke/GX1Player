#!/usr/bin/env python3
"""Enable LibVLC fast seeking for every media item on lower-powered GX1 hardware."""
from pathlib import Path
import sys

project = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
source = project / "app/src/main/java/com/example/gx1player/playback/Gx1LibVlcEngine.kt"
if not source.is_file():
    raise SystemExit(f"Missing LibVLC engine source: {source}")

text = source.read_text()
marker = "                      mediaPlayer.media = media"
option = 'media.addOption(":input-fast-seek")'
if option in text:
    print("LibVLC fast-seek option is already enabled.")
else:
    if text.count(marker) != 1:
        raise SystemExit(f"Expected one media assignment anchor, found {text.count(marker)}")
    insertion = (
        "                      // Prefer nearby keyframes over a slow frame-accurate scan on GX1.\n"
        "                      media.addOption(\":input-fast-seek\")\n"
    )
    text = text.replace(marker, insertion + marker, 1)
    source.write_text(text)
    print("Enabled LibVLC fast seeking for all formats before media is assigned.")

if text.count(option) != 1:
    raise SystemExit("Fast-seek option verification failed")
print("Verified exactly one :input-fast-seek option in Gx1LibVlcEngine.")
