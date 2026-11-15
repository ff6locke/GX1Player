from pathlib import Path

p = Path("gx1-player/app/src/main/java/com/example/gx1player/playback/Gx1LibVlcEngine.kt")
s = p.read_text()

# Keep the native LibVLC seek path; this patch only adds targeted diagnostics.
seek_method = "fun seekTo(positionMs: Long) { checkActive(); mediaPlayer.setTime(positionMs.coerceAtLeast(0L)) }"
if seek_method not in s:
    raise SystemExit("Expected original native LibVLC seek method; refusing an unverified rewrite.")

# Remove the previous per-event reflection query. It is not a reliable vout
# diagnostic and adds unnecessary work to every LibVLC callback.
block_start = s.find("val voutInfo = runCatching {")
if block_start >= 0:
    when_marker = "when (event.type) {"
    block_end = s.find(when_marker, block_start)
    if block_end < 0:
        raise SystemExit("Could not locate event dispatch after old vout reflection block.")
    line_start = s.rfind("\\n", 0, block_start) + 1
    when_line_start = s.rfind("\\n", 0, block_end) + 1
    if when_line_start <= line_start:
        raise SystemExit("Invalid old diagnostic block boundaries.")
    s = s[:line_start] + s[when_line_start:]

old_event = "mediaPlayer.setEventListener { event ->"
new_event = """mediaPlayer.setEventListener { event ->
            if (event.type != MediaPlayer.Event.TimeChanged &&
                event.type != MediaPlayer.Event.PositionChanged &&
                event.type != MediaPlayer.Event.LengthChanged) {
                android.util.Log.i(
                    "GX1-SEEK-DIAG",
                    "event=${event.type}, timeMs=${mediaPlayer.time}, playing=${mediaPlayer.isPlaying}"
                )
            }"""
if s.count(old_event) != 1:
    raise SystemExit("Expected exactly one LibVLC event listener.")
s = s.replace(old_event, new_event, 1)

s = s.replace(
    "if (seek > 0L) mediaPlayer.setTime(seek)",
    """if (seek > 0L) {
                        android.util.Log.i("GX1-SEEK-DIAG", "resumeSeek requestMs=$seek")
                        mediaPlayer.setTime(seek, false)
                        android.util.Log.i("GX1-SEEK-DIAG", "resumeSeek returned timeMs=${mediaPlayer.time}, playing=${mediaPlayer.isPlaying}")
                    }""",
    1
)

s = s.replace(
    seek_method,
    """fun seekTo(positionMs: Long) {
        checkActive()
        val targetMs = positionMs.coerceAtLeast(0L)
        android.util.Log.i(
            "GX1-SEEK-DIAG",
            "seekBefore targetMs=$targetMs currentMs=${mediaPlayer.time} lengthMs=${mediaPlayer.length} playing=${mediaPlayer.isPlaying}"
        )
        mediaPlayer.setTime(targetMs, false)
        android.util.Log.i(
            "GX1-SEEK-DIAG",
            "seekAfter targetMs=$targetMs currentMs=${mediaPlayer.time} lengthMs=${mediaPlayer.length} playing=${mediaPlayer.isPlaying}"
        )
    }""",
    1
)

if "mediaPlayer.setTime(targetMs, false)" not in s:
    raise SystemExit("Precise native seek call verification failed.")
if "GX1-SEEK-DIAG" not in s or "seekBefore targetMs=" not in s or "seekAfter targetMs=" not in s:
    raise SystemExit("Seek diagnostic verification failed.")
if 'media.addOption(":start-time=$startSeconds")' in s or "Large seek: reopening media" in s:
    raise SystemExit("Unexpected media-reopen workaround detected.")

p.write_text(s)
print("Added targeted LibVLC seek/event diagnostics; kept native precise seeking and playback/audio configuration unchanged.")
