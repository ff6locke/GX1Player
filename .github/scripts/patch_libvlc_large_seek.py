from pathlib import Path
import re

p = Path("gx1-player/app/src/main/java/com/example/gx1player/playback/Gx1LibVlcEngine.kt")
s = p.read_text()

# Keep every seek on LibVLC's native setTime() path. Do not reopen media,
# add :start-time, or detach/re-attach the video surface for large seeks.
native_seek = "fun seekTo(positionMs: Long) { checkActive(); mediaPlayer.setTime(positionMs.coerceAtLeast(0L)) }"
if native_seek not in s:
    raise SystemExit("Native LibVLC seek method not found; refusing an unverified seek rewrite.")

# Remove the per-event reflection/logging block using stable Kotlin markers.
# Avoid indentation-sensitive regex matching across workflow-injected diagnostics.
block_start = s.find("val voutInfo = runCatching {")
if block_start < 0:
    raise SystemExit("Could not find the per-event vout reflection block.")
when_marker = "when (event.type) {"
block_end = s.find(when_marker, block_start)
if block_end < 0:
    raise SystemExit("Could not find event dispatch after the vout reflection block.")
line_start = s.rfind("\n", 0, block_start) + 1
when_line_start = s.rfind("\n", 0, block_end) + 1
if when_line_start <= line_start:
    raise SystemExit("Invalid event-dispatch block boundaries.")
s = s[:line_start] + s[when_line_start:]

# Use LibVLC's precise-seek mode for both direct user seeks and restored resume
# positions. The default setTime overload can prefer fast/keyframe seeking, which
# is the path implicated by the GX1 large-seek freeze.
if s.count("mediaPlayer.setTime(positionMs.coerceAtLeast(0L))") != 1:
    raise SystemExit("Expected one direct seek call; refusing an ambiguous rewrite.")
if s.count("mediaPlayer.setTime(seek)") != 1:
    raise SystemExit("Expected one pending resume seek call; refusing an ambiguous rewrite.")
s = s.replace(
    "mediaPlayer.setTime(positionMs.coerceAtLeast(0L))",
    "mediaPlayer.setTime(positionMs.coerceAtLeast(0L), false)",
    1
)
s = s.replace("mediaPlayer.setTime(seek)", "mediaPlayer.setTime(seek, false)", 1)
if "mediaPlayer.setTime(positionMs.coerceAtLeast(0L), false)" not in s:
    raise SystemExit("Precise direct-seek verification failed.")
if "mediaPlayer.setTime(seek, false)" not in s:
    raise SystemExit("Precise resume-seek verification failed.")

# Verify the failed Build 1060 pre-play workaround is absent from this patch.
if 'media.addOption(":start-time=$startSeconds")' in s:
    raise SystemExit("Unexpected pre-play start-time option remains.")
if "Large seek: reopening media" in s:
    raise SystemExit("Unexpected media-reopen workaround remains.")

p.write_text(s)
print("Enabled precise LibVLC seeking for direct seeks and resume positions; removed per-event reflection/logging.")
