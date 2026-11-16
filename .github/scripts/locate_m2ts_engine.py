#!/usr/bin/env python3
from pathlib import Path
import sys
root = Path(sys.argv[1])
for p in sorted(root.rglob("*.kt")):
    try:
        data = p.read_text(errors="replace")
    except OSError:
        continue
    if "LibVLC" in data or "mediaPlayer.time" in data or "durationMs()" in data:
        print(f"ENGINE_CANDIDATE {p}")
        for i, line in enumerate(data.splitlines(), 1):
            if any(k in line for k in ("class Gx1LibVlcEngine", "fun currentTimeMs", "mediaPlayer.time", "fun durationMs", "mediaPlayer.position", "timeMs =")):
                print(f"{i}: {line[:240]}")
