from pathlib import Path

p = Path("gx1-player/app/src/main/java/com/example/gx1player/playback/Gx1LibVlcEngine.kt")
s = p.read_text()
old = "              fun seekTo(positionMs: Long) { checkActive(); mediaPlayer.setTime(positionMs.coerceAtLeast(0L)) }"
new = """              fun seekTo(positionMs: Long) {
                  checkActive()
                  val target = positionMs.coerceAtLeast(0L)
                  val current = currentTimeMs()
                  // Large jumps can leave the RockTek video output stalled while
                  // LibVLC audio and its playback clock continue. Reopen the same
                  // media at the requested timestamp to rebuild the video pipeline.
                  if (kotlin.math.abs(target - current) >= 300_000L) {
                      val uri = activeUri
                      if (uri != null) {
                          open(uri, target, activeDigitalOutput)
                          return
                      }
                  }
                  mediaPlayer.setTime(target)
              }"""
if old not in s:
    raise SystemExit("Expected LibVLC seek implementation not found; no source changed")
s = s.replace(old, new, 1)
if "Reopen the same" not in s or "open(uri, target, activeDigitalOutput)" not in s:
    raise SystemExit("Large-seek recovery verification failed")
p.write_text(s)
print("Large LibVLC seeks now reopen the current URI at the requested timestamp.")
