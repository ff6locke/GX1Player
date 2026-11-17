#!/usr/bin/env python3
"""Seek fix for LibVLC as the main engine.

Problems addressed (seek path only):
1. The Media3 controller clock opened the same file a second time, so every
   LibVLC playback had two demuxers reading one large MKV.
2. Each D-pad press sent a new precise seek before the previous one finished.
   Each new seek cancelled the one in flight, so holding a key never landed and
   the decoder stalled.
3. The D-pad target was built from VLC's current time, which does not move
   until a seek lands, so holding a key kept requesting nearly the same position.

Fix: the clock stays empty (no media, so its seeks are no-ops), and D-pad seeks
go through a queue. The queue keeps one seek in flight, builds each target from
the last requested position, and sends the latest target once the previous
seek has landed.
"""
from pathlib import Path
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
    text = text.replace(old, new)


# 1. The controller clock keeps its player object but never opens the file.
replace_once(
    "        clock.setMediaItem(MediaItem.fromUri(uri), resumeAt)\n"
    "        clock.prepare()\n",
    "        // LibVLC is the main engine. The controller clock must not open the file a second time.\n",
    "shadow clock media load",
)

# 2. Seek queue state and pump, declared at class level.
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

# 3. Hold-to-seek builds each target from the last requested position.
replace_once(
    "                    val current = engine?.currentTimeMs() ?: media3Player?.currentPosition ?: 0L\n",
    "                    val current = gx1PendingSeekMs\n"
    "                        ?: (if (gx1SeekInFlight) gx1SeekIssuedMs else null)\n"
    "                        ?: engine?.currentTimeMs() ?: media3Player?.currentPosition ?: 0L\n",
    "D-pad base position",
)

# 4. D-pad presses go through the queue, not straight to VLC.
replace_once(
    "                    if (engine != null) engine.seekTo(target) else media3Player?.seekTo(target)\n",
    "                    if (engine != null) gx1QueueSeek(target) else media3Player?.seekTo(target)\n",
    "D-pad seek call",
)

if "gx1QueueSeek(target)" not in text or "clock.prepare()" in text:
    raise SystemExit("Seek fix verification failed")

source.write_text(text)
print("LibVLC main seek fix applied: shadow clock no longer loads media; D-pad seeks are queued.")
