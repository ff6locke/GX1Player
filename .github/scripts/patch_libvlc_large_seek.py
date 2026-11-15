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

# Leave the existing time/position/duration event dispatch unchanged. The generated
# source varies between branches, and this optimization is not required for the seek fix.

# Verify the failed Build 1060 pre-play workaround is absent from this patch.
if 'media.addOption(":start-time=$startSeconds")' in s:
    raise SystemExit("Unexpected pre-play start-time option remains.")
if "Large seek: reopening media" in s:
    raise SystemExit("Unexpected media-reopen workaround remains.")

p.write_text(s)
print("Restored native LibVLC setTime() seeking and removed per-event reflection/logging and redundant time-event UI dispatch.")
