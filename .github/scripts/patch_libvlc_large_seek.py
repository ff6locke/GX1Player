from pathlib import Path
import re

p = Path("gx1-player/app/src/main/java/com/example/gx1player/playback/Gx1LibVlcEngine.kt")
s = p.read_text()

# Keep every seek on LibVLC's native setTime() path. Do not reopen media,
# add :start-time, or detach/re-attach the video surface for large seeks.
native_seek = "fun seekTo(positionMs: Long) { checkActive(); mediaPlayer.setTime(positionMs.coerceAtLeast(0L)) }"
if native_seek not in s:
    raise SystemExit("Native LibVLC seek method not found; refusing an unverified seek rewrite.")

# Remove the entire per-event diagnostics block, regardless of which later
# workflow step rewrote its Log.i call. Stop exactly at the event dispatch.
pattern = re.compile(
    r'(?ms)^([ \t]*)val voutInfo = runCatching \{.*?^\1when \(event\.type\)\n'
)
s, removed = pattern.subn(r"\1when (event.type)\n", s, count=1)
if removed != 1:
    raise SystemExit(f"Expected one per-event diagnostics block before event dispatch; found {removed}.")

# The main playback UI polls current position/duration independently. These
# event callbacks need not dispatch redundant UI state updates.
old = """                          MediaPlayer.Event.TimeChanged,
                          MediaPlayer.Event.PositionChanged,
                          MediaPlayer.Event.LengthChanged -> publish()"""
new = """                          MediaPlayer.Event.TimeChanged,
                          MediaPlayer.Event.PositionChanged,
                          MediaPlayer.Event.LengthChanged -> Unit"""
if s.count(old) != 1:
    raise SystemExit(f"Expected one time-event publish block; found {s.count(old)}.")
s = s.replace(old, new, 1)

# Verify the failed Build 1060 pre-play workaround is absent from this patch.
if 'media.addOption(":start-time=$startSeconds")' in s:
    raise SystemExit("Unexpected pre-play start-time option remains.")
if "Large seek: reopening media" in s:
    raise SystemExit("Unexpected media-reopen workaround remains.")

p.write_text(s)
print("Restored native LibVLC setTime() seeking and removed per-event reflection/logging and redundant time-event UI dispatch.")
