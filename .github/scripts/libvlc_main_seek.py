#!/usr/bin/env python3
"""Seek fix for LibVLC as the main engine.

The Media3 controller clock must not open a second copy of the video.
D-pad seeks are serialized so a new precise seek does not cancel one still
being decoded, and hold-to-seek targets build from the last requested position.
"""
from pathlib import Path
import re
import sys

project = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
source = project / "app/src/main/java/com/example/gx1player/MainActivity.kt"
if not source.is_file():
    raise SystemExit(f"Missing MainActivity source: {source}")

text = source.read_text()


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    text = text.replace(old, new, 1)


# Support both controller-clock constructions used by the uploaded workflow
# and older source revisions.
clock_patterns = [
    "        clock.setMediaItem(buildMediaItem(uri), resumeAt)\n"
    "        clock.prepare()\n",
    "        clock.setMediaItem(MediaItem.fromUri(uri), resumeAt)\n"
    "        clock.prepare()\n",
]
matches = [pattern for pattern in clock_patterns if text.count(pattern)]
if len(matches) != 1:
    raise SystemExit(
        "shadow clock media load: expected exactly one supported clock pattern, "
        f"found {len(matches)}"
    )
replace_once(
    matches[0],
    "        // LibVLC is the main engine. The controller clock must not open the file a second time.\n",
    "shadow clock media load",
)

replace_once(
    "    private var gx1SeekSessionProgressMs = 0L\n",
    "    private var gx1SeekSessionProgressMs = 0L\n"
    "    private var gx1PendingSeekMs: Long? = null\n"
    "    private var gx1SeekInFlight = false\n"
    "    private var gx1SeekIssuedMs = 0L\n"
    "    private var gx1SeekIssuedAt = 0L\n"
    "    private val gx1SeekHandler = android.os.Handler(android.os.Looper.getMainLooper())\n"
    "    private val gx1SeekPump = Runnable { gx1PumpSeek() }\n"
    "\n"
    "    /** Queues a LibVLC seek. Only one seek is in flight; the newest target is sent when it lands. */\n"
    "    private fun gx1QueueSeek(target: Long) {\n"
    "        gx1PendingSeekMs = target\n"
    "        gx1SeekHandler.removeCallbacks(gx1SeekPump)\n"
    "        gx1PumpSeek()\n"
    "    }\n"
    "\n"
    "    private fun gx1PumpSeek() {\n"
    "        val engineNow = mainVlcEngine ?: run {\n"
    "            gx1PendingSeekMs = null\n"
    "            gx1SeekInFlight = false\n"
    "            return\n"
    "        }\n"
    "        val now = android.os.SystemClock.elapsedRealtime()\n"
    "        if (gx1SeekInFlight) {\n"
    "            val landed = kotlin.math.abs(engineNow.currentTimeMs() - gx1SeekIssuedMs) <= 1_500L ||\n"
    "                now - gx1SeekIssuedAt >= 8_000L\n"
    "            if (!landed) {\n"
    "                gx1SeekHandler.postDelayed(gx1SeekPump, 200L)\n"
    "                return\n"
    "            }\n"
    "            gx1SeekInFlight = false\n"
    "        }\n"
    "        val target = gx1PendingSeekMs ?: return\n"
    "        gx1PendingSeekMs = null\n"
    "        gx1SeekInFlight = true\n"
    "        gx1SeekIssuedMs = target\n"
    "        gx1SeekIssuedAt = now\n"
    "        engineNow.seekTo(target)\n"
    "        gx1SeekHandler.postDelayed(gx1SeekPump, 200L)\n"
    "    }\n",
    "seek queue declarations",
)

replace_once(
    "                    val current = engine?.currentTimeMs() ?: media3Player?.currentPosition ?: 0L\n",
    "                    val current = gx1PendingSeekMs\n"
    "                        ?: (if (gx1SeekInFlight) gx1SeekIssuedMs else null)\n"
    "                        ?: engine?.currentTimeMs() ?: media3Player?.currentPosition ?: 0L\n",
    "D-pad base position",
)

replace_once(
    "                    if (engine != null) engine.seekTo(target) else media3Player?.seekTo(target)\n",
    "                    if (engine != null) gx1QueueSeek(target) else media3Player?.seekTo(target)\n",
    "D-pad seek call",
)

if "gx1QueueSeek(target)" not in text or "clock.prepare()" in text:
    raise SystemExit("Seek fix verification failed")

source.write_text(text)
print("LibVLC main seek fix applied: shadow clock no longer loads media; D-pad seeks are queued.")


# Ask LibVLC for a fast keyframe seek. Accurate seeks on long-GOP 4K HEVC
# streams can leave the GX1 decoding for tens of seconds after a large jump.
engine = project / "app/src/main/java/com/example/gx1player/playback/Gx1LibVlcEngine.kt"
if not engine.is_file():
    raise SystemExit(f"Missing generated LibVLC engine: {engine}")
engine_text = engine.read_text()
seek_pattern = re.compile(
    r"fun seekTo\(positionMs: Long\)\s*\{\s*checkActive\(\);\s*"
    r"mediaPlayer\.setTime\(positionMs\.coerceAtLeast\(0L\)\)\s*\}"
)
engine_text, seek_count = seek_pattern.subn(
    "fun seekTo(positionMs: Long) { checkActive(); mediaPlayer.setTime(positionMs.coerceAtLeast(0L), true) }",
    engine_text,
    count=1,
)
if seek_count != 1:
    raise SystemExit(f"LibVLC seek method: expected one match, found {seek_count}")
engine.write_text(engine_text)
print("LibVLC D-pad seeking now requests fast keyframe positioning.")

# Do not write directly to Media3's TimeBar from a second timer.
# PlayerControlView owns its own progress refresh; competing updates made the
# bar jump back to zero and then forward to LibVLC's current position.
