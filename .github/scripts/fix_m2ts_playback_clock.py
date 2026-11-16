#!/usr/bin/env python3
"""Use LibVLC's normalized playback position for TS/M2TS transport controls."""
from pathlib import Path
import sys

project = Path(sys.argv[1])
source = project / "app/src/main/java/com/example/gx1player/playback/Gx1LibVlcEngine.kt"
if not source.is_file():
    raise SystemExit(f"Missing LibVLC engine source: {source}")

text = source.read_text()
changes = 0

old = "    private var activeDigitalOutput = true\n"
new = old + "    @Volatile private var useNormalizedPositionClock = false\n"
if old in text and "useNormalizedPositionClock" not in text:
    text = text.replace(old, new, 1)
    changes += 1

old = """        activeUri = uri
        activeDigitalOutput = digitalOutput
        reachedEnd = false
"""
new = """        activeUri = uri
        activeDigitalOutput = digitalOutput
        useNormalizedPositionClock = uri.lastPathSegment
            ?.substringAfterLast('.', "")
            ?.lowercase() in setOf("ts", "m2ts", "mts")
        reachedEnd = false
"""
if old in text:
    text = text.replace(old, new, 1)
    changes += 1

old = """    fun currentTimeMs(): Long = if (released) 0L else mediaPlayer.time.coerceAtLeast(0L)
"""
new = """    fun currentTimeMs(): Long {
        if (released) return 0L
        val timeMs = mediaPlayer.time.coerceAtLeast(0L)
        if (!useNormalizedPositionClock) return timeMs
        val duration = durationMs()
        val position = mediaPlayer.position
        if (duration > 0L && position.isFinite() && position > 0f) {
            return (duration.toDouble() * position.coerceIn(0f, 1f).toDouble())
                .toLong().coerceIn(0L, duration)
        }
        return timeMs
    }
"""
if old in text:
    text = text.replace(old, new, 1)
    changes += 1

old = """            timeMs = mediaPlayer.time.coerceAtLeast(0L),
"""
new = """            timeMs = currentTimeMs(),
"""
if old in text:
    text = text.replace(old, new, 1)
    changes += 1

if changes != 4:
    raise SystemExit(f"Expected 4 source changes, applied {changes}; refusing partial patch.")
source.write_text(text)
print("Patched TS/M2TS/MTS transport clock to use LibVLC normalized position.")
