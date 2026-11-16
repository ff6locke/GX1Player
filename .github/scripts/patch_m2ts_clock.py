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

# Resolve extensions from the content-provider display name. MediaStore URIs often
# end in a numeric row ID, so lastPathSegment is not a reliable filename.
if "activeFileExtension" not in s:
    anchor = "    private var activeUri: Uri? = null"
    if s.count(anchor) != 1:
        raise SystemExit("Could not find activeUri field")
    s = s.replace(anchor, anchor + '\n    @Volatile private var activeFileExtension = ""', 1)

if "private fun resolveFileExtension(uri: Uri): String" not in s:
    anchor = "    fun open(uri: Uri, startPositionMs: Long = 0L, digitalOutput: Boolean = true) {"
    helper = """    private fun resolveFileExtension(uri: Uri): String {
        val displayName = runCatching {
            appContext.contentResolver.query(
                uri, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME), null, null, null
            )?.use { cursor ->
                if (cursor.moveToFirst()) cursor.getString(0) else null
            }
        }.getOrNull()
        val name = displayName ?: uri.lastPathSegment.orEmpty()
        return name.substringAfterLast('/', name).substringAfterLast('.', "").lowercase()
    }

"""
    if s.count(anchor) != 1:
        raise SystemExit("Could not find unique open method")
    s = s.replace(anchor, helper + anchor, 1)

s = re.sub(
    r'uri\.lastPathSegment\?\.substringAfterLast\(\'\.\', ""\)\?\.lowercase\(\) in setOf\("ts", "m2ts", "mts"\)',
    'activeFileExtension in setOf("ts", "m2ts", "mts")',
    s
)
s = re.sub(
    r'activeUri\?\.lastPathSegment\?\.substringAfterLast\(\'\.\', ""\)\?\.lowercase\(\) in setOf\("m2ts", "mts"\)',
    'activeFileExtension in setOf("m2ts", "mts")',
    s
)
open_anchor = "        activeUri = uri"
if "activeFileExtension = resolveFileExtension(uri)" not in s:
    if s.count(open_anchor) != 1:
        raise SystemExit("Could not find activeUri assignment in open")
    s = s.replace(open_anchor, open_anchor + "\n        activeFileExtension = resolveFileExtension(uri)", 1)


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
    }
    fun setRate(rate: Float) {
        checkActive()
        mediaPlayer.setRate(rate.coerceIn(0.25f, 4.0f))
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

# Preserve the existing Paused event line so later video-output patches can anchor on it.

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

# Reset the fallback clock for every newly opened source. Without this,
# a previous M2TS file's elapsed position can leak into the next file.
open_reset_anchor = "        activeFileExtension = resolveFileExtension(uri)"
if "m2tsClockBaseMs = startPositionMs.coerceAtLeast(0L)" not in s:
    if s.count(open_reset_anchor) != 1:
        raise SystemExit("Could not find unique active file extension assignment")
    s = s.replace(open_reset_anchor, open_reset_anchor + """
        m2tsClockBaseMs = startPositionMs.coerceAtLeast(0L)
        m2tsClockStartedAtMs = android.os.SystemClock.elapsedRealtime()
        m2tsClockRunning = false""", 1)

# Keep the fallback clock's state in sync with LibVLC pause/stop/end events.
s = s.replace(
    "MediaPlayer.Event.Paused -> publish(playing = false)",
    "MediaPlayer.Event.Paused -> { m2tsClockRunning = false; publish(playing = false) }"
)
s = s.replace(
    "MediaPlayer.Event.Stopped -> publish(playing = false, opening = false)",
    "MediaPlayer.Event.Stopped -> { m2tsClockRunning = false; publish(playing = false, opening = false) }"
)
s = s.replace(
    "reachedEnd = true\n                    publish(playing = false, opening = false, ended = true)",
    "reachedEnd = true\n                    m2tsClockRunning = false\n                    publish(playing = false, opening = false, ended = true)"
)
s = s.replace(
    "m2tsClockBaseMs = maxOf(m2tsClockBaseMs, seek)",
    "m2tsClockBaseMs = seek.coerceAtLeast(0L)"
)

# Some Android builds cannot extract M2TS duration through MetadataRetriever.
# Ask MediaExtractor as a second independent duration source.
if "gx1-m2ts-extractor-duration-probe" not in s:
    probe_anchor = '''        if (activeFileExtension in setOf("ts", "m2ts", "mts")) {
            Thread({'''
    probe_end = '''            }, "gx1-duration-probe").apply {
                isDaemon = true
                start()
            }
        }
'''
    if s.count(probe_end) != 1:
        raise SystemExit("Could not find unique metadata duration-probe end")
    extractor_probe = '''
        if (activeFileExtension in setOf("ts", "m2ts", "mts")) {
            Thread({
                val extractor = android.media.MediaExtractor()
                val extracted = try {
                    extractor.setDataSource(appContext, uri, null)
                    (0 until extractor.trackCount).mapNotNull { index ->
                        val format = extractor.getTrackFormat(index)
                        if (format.containsKey(android.media.MediaFormat.KEY_DURATION))
                            format.getLong(android.media.MediaFormat.KEY_DURATION) / 1000L
                        else null
                    }.maxOrNull() ?: 0L
                } catch (_: Exception) {
                    0L
                } finally {
                    runCatching { extractor.release() }
                }
                if (durationGeneration == sourceGeneration && extracted > 0L &&
                    (durationHintMs <= 0L || extracted > durationHintMs)) {
                    durationHintMs = extracted
                    publish()
                }
            }, "gx1-m2ts-extractor-duration-probe").apply {
                isDaemon = true
                start()
            }
        }
'''
    s = s.replace(probe_end, probe_end + extractor_probe, 1)

# Allow the UI's Media3 timeline duration to drive normalized M2TS seeking
# when LibVLC itself reports an unknown duration.
s = s.replace(
    "fun seekTo(positionMs: Long) {",
    "fun seekTo(positionMs: Long, durationOverrideMs: Long = durationMs()) {",
    1
)
s = s.replace(
    "val duration = durationMs()\n        if (usesNormalizedPositionClock() && duration > 0L) {",
    "val duration = durationOverrideMs.takeIf { it > 0L } ?: durationMs()\n        if (usesNormalizedPositionClock() && duration > 0L) {",
    1
)

required = [
    "m2tsClockBaseMs = target",
    "val estimate = m2tsClockBaseMs",
    "timeMs = currentTimeMs()",
    "gx1-m2ts-clock-poll",
    "pos > 0f",
    "resolveFileExtension(uri)",
    "activeFileExtension in setOf(\"m2ts\", \"mts\")",
]
missing = [marker for marker in required if marker not in s]
if missing:
    raise SystemExit("M2TS clock patch verification failed: " + ", ".join(missing))

source.write_text(s)
print("Applied and verified provider-filename extension detection, M2TS/MTS monotonic clock fallback, normalized seeking and 500 ms polling.")
