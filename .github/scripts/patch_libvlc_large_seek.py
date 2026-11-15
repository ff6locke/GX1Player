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
    // For large jumps, reopen at the target before playback starts. A post-Playing
    // setTime() was leaving both audio and video stalled on some GX1 decoders.
    if (kotlin.math.abs(target - current) >= 300_000L) {
        val uri = activeUri
        if (uri != null) {
            android.util.Log.i("GX1-VLC", "Large seek: reopening media with pre-play start-time at $target ms")
            open(uri, target, activeDigitalOutput)
            return
        }
    }
    mediaPlayer.setTime(target)
}"""
replacement = "\n".join(indent + line if line else "" for line in seek_method.splitlines())
s = s[:seek_matches[0].start()] + replacement + s[seek_matches[0].end():]

open_start = s.find("fun open(uri: Uri")
open_end = s.find("fun play()", open_start)
if open_start < 0 or open_end < 0:
    raise SystemExit("Could not locate LibVLC open() method boundaries.")
open_body = s[open_start:open_end]

pending_line = "pendingSeekMs = startPositionMs.coerceAtLeast(0L)"
if open_body.count(pending_line) != 1:
    raise SystemExit("Could not uniquely locate pending seek assignment in open().")
open_body = open_body.replace(
    pending_line,
    """// Apply non-zero start positions as a media input option before play().
                  // Avoid seeking immediately after the Playing event, which can stall
                  // both audio and video on the GX1 hardware decoder.
                  pendingSeekMs = 0L""",
    1
)

media_assignment = "mediaPlayer.media = media"
if open_body.count(media_assignment) != 1:
    raise SystemExit("Could not uniquely locate media assignment in open().")
open_body = open_body.replace(
    media_assignment,
    """if (startPositionMs > 0L) {
                          val startSeconds = startPositionMs.toDouble() / 1000.0
                          media.addOption(":start-time=$startSeconds")
                          android.util.Log.i("GX1-VLC", "Configured pre-play start-time=$startSeconds seconds")
                      }
                      mediaPlayer.media = media""",
    1
)

# Remove the prior surface detach/reattach workaround: it did not recover audio
# and is unnecessary when the media starts at the requested position.
field = "private var rebuildVideoOutputOnNextOpen = false"
s = s.replace("\n              " + field, "", 1)
s = s.replace("\n    " + field, "", 1)

s = s[:open_start] + open_body + s[open_end:]

if "media.addOption(\":start-time=$startSeconds\")" not in s:
    raise SystemExit("Pre-play start-time option was not inserted.")
if "pendingSeekMs = 0L" not in s:
    raise SystemExit("Post-Playing seek was not disabled.")
if "Rebinding VLC video output after large seek" in s:
    raise SystemExit("Old surface-rebind workaround unexpectedly remains.")

p.write_text(s)
print("Large seeks now use LibVLC's pre-play start-time option; no post-Playing seek or surface rebind.")
