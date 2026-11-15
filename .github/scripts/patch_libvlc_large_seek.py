from pathlib import Path
import re

p = Path("gx1-player/app/src/main/java/com/example/gx1player/playback/Gx1LibVlcEngine.kt")
s = p.read_text()

seek_pattern = re.compile(
    r"(?m)^(?P<indent>[ \t]*)fun seekTo\(positionMs: Long\)[ \t]*\{[^}]*\}"
)
seek_matches = list(seek_pattern.finditer(s))
if len(seek_matches) != 1:
    raise SystemExit(f"Expected exactly one seekTo method; found {len(seek_matches)}.")

indent = seek_matches[0].group("indent")
seek_method = """fun seekTo(positionMs: Long) {
    checkActive()
    val target = positionMs.coerceAtLeast(0L)
    val current = currentTimeMs()
    // Reopen the media and explicitly rebind the video surface for large jumps.
    if (kotlin.math.abs(target - current) >= 300_000L) {
        val uri = activeUri
        if (uri != null) {
            rebuildVideoOutputOnNextOpen = true
            open(uri, target, activeDigitalOutput)
            return
        }
    }
    mediaPlayer.setTime(target)
}"""
replacement = "\n".join(indent + line if line else "" for line in seek_method.splitlines())
s = s[:seek_matches[0].start()] + replacement + s[seek_matches[0].end():]

# Add a one-shot flag beside the attached layout reference.
anchor = "private var attachedLayout: VLCVideoLayout? = null"
if "private var rebuildVideoOutputOnNextOpen" not in s:
    if s.count(anchor) != 1:
        raise SystemExit("Could not uniquely locate attachedLayout field.")
    s = s.replace(anchor, anchor + "\n    private var rebuildVideoOutputOnNextOpen = false", 1)

# Rebind the actual VLCVideoLayout after assigning the new media, before play().
play_anchor = "media.release()\n                  android.util.Log.i(android.util.Log.i"
# Use the unique media-release/log sequence from the engine's open() implementation.
needle = """media.release()
                  android.util.Log.i("GX1-VLC", "Opened media using ${uri.scheme} source; digitalOutput=$digitalOutput")
                  mediaPlayer.play()"""
insert = """media.release()
                  if (rebuildVideoOutputOnNextOpen) {
                      rebuildVideoOutputOnNextOpen = false
                      val layout = attachedLayout
                      if (layout != null) {
                          android.util.Log.i("GX1-VLC", "Rebinding VLC video output after large seek")
                          mediaPlayer.detachViews()
                          mediaPlayer.attachViews(layout, null, true, false)
                          attachedLayout = layout
                      } else {
                          android.util.Log.w("GX1-VLC", "Cannot rebind video output: no attached VLCVideoLayout")
                      }
                  }
                  android.util.Log.i("GX1-VLC", "Opened media using ${uri.scheme} source; digitalOutput=$digitalOutput")
                  mediaPlayer.play()"""
if s.count(needle) != 1:
    raise SystemExit(f"Could not uniquely locate open() media/play sequence; found {s.count(needle)}.")
s = s.replace(needle, insert, 1)

required = [
    "private var rebuildVideoOutputOnNextOpen = false",
    "rebuildVideoOutputOnNextOpen = true",
    "Rebinding VLC video output after large seek",
    "mediaPlayer.attachViews(layout, null, true, false)",
]
missing = [x for x in required if x not in s]
if missing:
    raise SystemExit("Video-output recovery verification failed: " + ", ".join(missing))
p.write_text(s)
print("Large seeks now reopen the source and rebind VLCVideoLayout before playback resumes.")
