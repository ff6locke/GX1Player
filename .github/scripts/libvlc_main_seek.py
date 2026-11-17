#!/usr/bin/env python3
"""Serialize D-pad seeks through the main LibVLC engine.

The Media3 controller clock is kept as a UI-only player and must not open a
second copy of the video. A single LibVLC seek is allowed in flight; newer
D-pad targets are queued and sent when the previous seek settles.
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
    text = text.replace(old, new, 1)


# Do not let the Media3 controller clock open the same large file a second time.
clock_item = (
    "        clock.setMediaItem(buildMediaItem(uri), resumeAt)\n"
    "        clock.prepare()\n"
)
clock_item_legacy = (
    "        clock.setMediaItem(MediaItem.fromUri(uri), resumeAt)\n"
    "        clock.prepare()\n"
)
if clock_item in text:
    text = text.replace(
        clock_item,
        "        // LibVLC is the main engine; keep this Media3 controller clock media-free.\n",
        1,
    )
elif clock_item_legacy in text:
    text = text.replace(
        clock_item_legacy,
        "        // LibVLC is the main engine; keep this Media3 controller clock media-free.\n",
        1,
    )
elif "clock.prepare()" not in text and "clock.setMediaItem(buildMediaItem(uri), resumeAt)" not in text:
    pass
else:
    raise SystemExit("Could not safely locate the Media3 shadow-clock media load")

# Queue state and a single-seek pump, declared at class level.
progress_line = "    private var gx1SeekSessionProgressMs = 0L\n"
queue_state = """    private var gx1SeekPendingTargetMs: Long? = null
    private var gx1SeekInFlight = false
    private var gx1SeekIssuedTargetMs = 0L
    private var gx1SeekIssuedAtMs = 0L
    private val gx1SeekHandler = android.os.Handler(android.os.Looper.getMainLooper())
    private val gx1SeekPump = Runnable { gx1PumpSeekQueue() }

    private fun gx1QueueSeek(targetMs: Long) {
        gx1SeekPendingTargetMs = targetMs
        gx1SeekHandler.removeCallbacks(gx1SeekPump)
        gx1PumpSeekQueue()
    }

    private fun gx1PumpSeekQueue() {
        val engine = mainVlcEngine ?: run {
            gx1SeekPendingTargetMs = null
            gx1SeekInFlight = false
            return
        }
        val now = android.os.SystemClock.elapsedRealtime()
        if (gx1SeekInFlight) {
            val landed = kotlin.math.abs(engine.currentTimeMs() - gx1SeekIssuedTargetMs) <= 1_500L ||
                now - gx1SeekIssuedAtMs >= 8_000L
            if (!landed) {
                gx1SeekHandler.postDelayed(gx1SeekPump, 200L)
                return
            }
            gx1SeekInFlight = false
        }
        val target = gx1SeekPendingTargetMs ?: return
        gx1SeekPendingTargetMs = null
        gx1SeekInFlight = true
        gx1SeekIssuedTargetMs = target
        gx1SeekIssuedAtMs = now
        engine.seekTo(target)
        gx1SeekHandler.postDelayed(gx1SeekPump, 200L)
    }

"""
if "private fun gx1QueueSeek(targetMs: Long)" not in text:
    if text.count(progress_line) != 1:
        raise SystemExit("Could not locate unique seek-session state insertion point")
    text = text.replace(progress_line, progress_line + queue_state, 1)

replace_once(
    "                    val current = engine?.currentTimeMs() ?: media3Player?.currentPosition ?: 0L\n",
    "                    val current = gx1SeekPendingTargetMs\n"
    "                        ?: (if (gx1SeekInFlight) gx1SeekIssuedTargetMs else null)\n"
    "                        ?: engine?.currentTimeMs() ?: media3Player?.currentPosition ?: 0L\n",
    "D-pad seek base position",
)
replace_once(
    "                    if (engine != null) engine.seekTo(target) else media3Player?.seekTo(target)\n",
    "                    if (engine != null) gx1QueueSeek(target) else media3Player?.seekTo(target)\n",
    "D-pad seek dispatch",
)

if "gx1QueueSeek(target)" not in text or "clock.prepare()" in text:
    raise SystemExit("Queued LibVLC seek verification failed")

source.write_text(text)
print("Applied serialized LibVLC D-pad seeks; the controller clock no longer opens a second media source.")
