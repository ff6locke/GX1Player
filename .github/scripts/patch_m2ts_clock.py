from pathlib import Path
import re
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else "gx1-player")
if not root.exists():
    raise SystemExit(f"Extracted project directory does not exist: {root}")

# The source ZIP has changed its package/layout over time. Locate the engine
# by its class declaration rather than assuming a package path.
candidates = []
for path in root.rglob("*.kt"):
    try:
        data = path.read_text(errors="replace")
    except OSError:
        continue
    if re.search(r"\bclass\s+Gx1LibVlcEngine\b", data):
        candidates.append((path, data))

if len(candidates) != 1:
    found = ", ".join(str(path) for path, _ in candidates) or "none"
    raise SystemExit(
        f"Expected exactly one Gx1LibVlcEngine Kotlin source under {root}; "
        f"found {len(candidates)}: {found}"
    )

source, s = candidates[0]
print(f"Located LibVLC engine source: {source}")

def replace_method(name, body):
    global s
    pattern = rf"(?ms)^(    fun {name}\([^)]*\): [^{{\n]+\{{).*?^(    \}})"
    s2, count = re.subn(pattern, body, s, count=1)
    if count != 1:
        raise SystemExit(f"Could not replace unique {name} method (matches={count})")
    s = s2

if "usesNormalizedPositionClock()" not in s:
    anchor = "    fun seekTo(positionMs: Long) {"
    if s.count(anchor) != 1:
        raise SystemExit("Could not find unique seekTo method")
    s = s.replace(anchor, """    private fun usesNormalizedPositionClock(): Boolean =
        activeUri?.lastPathSegment?.substringAfterLast('.', "")?.lowercase() in setOf("m2ts", "mts")

    fun seekTo(positionMs: Long) {""", 1)

if "m2tsClockBaseMs" not in s:
    anchor = "    private var activeDigitalOutput = true"
    if s.count(anchor) != 1:
        raise SystemExit("Could not find clock field insertion point")
    s = s.replace(anchor, anchor + """
    @Volatile private var m2tsClockBaseMs = 0L
    @Volatile private var m2tsClockStartedAtMs = 0L
    @Volatile private var m2tsClockRunning = false""", 1)

# Replace the existing methods as a single bounded region using their exact signatures.
seek_start = s.find("    fun seekTo(positionMs: Long) {")
time_start = s.find("    fun currentTimeMs(): Long {", seek_start)
if seek_start < 0 or time_start < 0:
    raise SystemExit("Could not locate seek/time methods")
time_end = s.find("\n    }", time_start) + len("\n    }")
if time_end < len("\n    }"):
    raise SystemExit("Could not locate end of currentTimeMs")
seek_body = """    fun seekTo(positionMs: Long) {
        checkActive()
        val target = positionMs.coerceAtLeast(0L)
        val duration = durationMs()
        if (usesNormalizedPositionClock() && duration > 0L) {
            mediaPlayer.setPosition((target.toDouble() / duration.toDouble()).toFloat().coerceIn(0f, 1f))
            m2tsClockBaseMs = target
            m2tsClockStartedAtMs = android.os.SystemClock.elapsedRealtime()
            m2tsClockRunning = mediaPlayer.isPlaying
        } else {
            mediaPlayer.setTime(target)
        }
    }"""
time_body = """    fun currentTimeMs(): Long {
        if (released) return 0L
        if (!usesNormalizedPositionClock()) return mediaPlayer.time.coerceAtLeast(0L)
        val duration = durationMs()
        val time = runCatching { mediaPlayer.time }.getOrDefault(0L).coerceAtLeast(0L)
        val pos = runCatching { mediaPlayer.position }.getOrDefault(-1f)
        val normalized = if (duration > 0L && pos.isFinite() && pos > 0f) {
            (pos.coerceIn(0f, 1f).toDouble() * duration).toLong()
        } else 0L
        val reported = maxOf(time, normalized)
        val now = android.os.SystemClock.elapsedRealtime()
        if (reported > m2tsClockBaseMs) {
            m2tsClockBaseMs = reported
            m2tsClockStartedAtMs = now
        }
        if (m2tsClockRunning && mediaPlayer.isPlaying) {
            val estimate = m2tsClockBaseMs + (now - m2tsClockStartedAtMs).coerceAtLeast(0L)
            return if (duration > 0L) estimate.coerceAtMost(duration) else estimate
        }
        return maxOf(m2tsClockBaseMs, reported)
    }"""
s = s[:seek_start] + seek_body + "\n\n" + time_body + s[time_end:]

s = s.replace("timeMs = mediaPlayer.time.coerceAtLeast(0L),", "timeMs = currentTimeMs(),", 1)

play_anchor = "                    if (seek > 0L) mediaPlayer.setTime(seek)"
if "m2tsClockRunning = true" not in s:
    if s.count(play_anchor) != 1:
        raise SystemExit("Could not find unique Playing event clock anchor")
    s = s.replace(play_anchor, play_anchor + """
                    if (usesNormalizedPositionClock()) {
                        m2tsClockBaseMs = maxOf(m2tsClockBaseMs, seek)
                        m2tsClockStartedAtMs = android.os.SystemClock.elapsedRealtime()
                        m2tsClockRunning = true
                    }""", 1)

pause_anchor = "                MediaPlayer.Event.Paused -> publish(playing = false)"
if pause_anchor in s:
    s = s.replace(pause_anchor, """                MediaPlayer.Event.Paused -> {
                    if (usesNormalizedPositionClock()) {
                        m2tsClockBaseMs = currentTimeMs()
                        m2tsClockRunning = false
                    }
                    publish(playing = false)
                }""", 1)

if "gx1-m2ts-clock-poll" not in s:
    init_end = "    }\n    fun attach(layout: VLCVideoLayout)"
    if s.count(init_end) != 1:
        raise SystemExit("Could not find unique init/attach boundary for polling thread")
    poller = """        Thread({
            while (!released) {
                try { Thread.sleep(500L) } catch (_: InterruptedException) { return@Thread }
                if (!released && usesNormalizedPositionClock() && mediaPlayer.isPlaying) {
                    runCatching { publish() }
                }
            }
        }, "gx1-m2ts-clock-poll").apply { isDaemon = true; start() }
    }
    fun attach(layout: VLCVideoLayout)"""
    s = s.replace(init_end, poller, 1)

required = [
    "m2tsClockBaseMs = target",
    "val estimate = m2tsClockBaseMs",
    "timeMs = currentTimeMs()",
    "gx1-m2ts-clock-poll",
    "pos > 0f",
]
missing = [marker for marker in required if marker not in s]
if missing:
    raise SystemExit("M2TS clock patch verification failed: " + ", ".join(missing))

source.write_text(s)
print("Applied and verified M2TS/MTS monotonic clock fallback, normalized seeking, pause handling and 500 ms polling.")
