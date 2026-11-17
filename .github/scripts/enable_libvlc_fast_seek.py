#!/usr/bin/env python3
"""Keep LibVLC seeking aligned with VLC for Android defaults."""
from pathlib import Path
import sys

project = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
source = project / "app/src/main/java/com/example/gx1player/playback/Gx1LibVlcEngine.kt"
if not source.is_file():
    raise SystemExit(f"Missing LibVLC engine source: {source}")

text = source.read_text()
lines = text.splitlines(keepends=True)
filtered = [line for line in lines if 'media.addOption(":input-fast-seek")' not in line]
removed = len(lines) - len(filtered)
text = ''.join(filtered)
if ":input-fast-seek" in text:
    raise SystemExit("Unexpected forced input-fast-seek option remains")
source.write_text(text)
print(f"Removed {removed} forced input-fast-seek option(s); VLC default seek mode is preserved.")
