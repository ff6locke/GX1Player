from pathlib import Path

p = Path("gx1-player/app/src/main/java/com/example/gx1player/playback/Gx1LibVlcEngine.kt")
s = p.read_text()

old = "fun seekTo(positionMs: Long) { checkActive(); mediaPlayer.setTime(positionMs.coerceAtLeast(0L)) }"
new = """fun seekTo(positionMs: Long) {
        checkActive()
        val targetMs = positionMs.coerceAtLeast(0L)
        // Accurate seeking avoids the fast-seek Matroska cluster shortcut that
        // previously left some high-bitrate files stalled after large jumps.
        mediaPlayer.setTime(targetMs, false)
    }"""

if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    raise SystemExit("Expected LibVLC seek method was not found; refusing an unverified patch.")

old_resume = "if (seek > 0L) mediaPlayer.setTime(seek)"
new_resume = "if (seek > 0L) mediaPlayer.setTime(seek, false)"
if old_resume in s:
    s = s.replace(old_resume, new_resume, 1)

if "mediaPlayer.setTime(targetMs, false)" not in s:
    raise SystemExit("Accurate seek verification failed.")
if "mediaPlayer.setTime(targetMs, fastSeek)" in s:
    raise SystemExit("Fast-seek path remains.")
p.write_text(s)
print("Applied accurate LibVLC seeking for manual seeks and resume seeks.")
