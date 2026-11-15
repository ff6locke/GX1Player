from pathlib import Path
import re

p = Path("gx1-player/app/src/main/java/com/example/gx1player/playback/Gx1LibVlcEngine.kt")
s = p.read_text()

pattern = re.compile(
    r"(?m)^(?P<indent>[ \t]*)fun seekTo\(positionMs: Long\)[ \t]*\{[^}]*\}"
)
matches = list(pattern.finditer(s))
if len(matches) != 1:
    raise SystemExit(
        "Expected exactly one LibVLC seekTo(positionMs) method; found "
        + str(len(matches)) + ". No source changed."
    )

indent = matches[0].group("indent")
new = """fun seekTo(positionMs: Long) {
    checkActive()
    val target = positionMs.coerceAtLeast(0L)
    val current = currentTimeMs()
    // Rebuild LibVLC's video output after a large seek on RockTek GX1.
    if (kotlin.math.abs(target - current) >= 300_000L) {
        val uri = activeUri
        if (uri != null) {
            open(uri, target, activeDigitalOutput)
            return
        }
    }
    mediaPlayer.setTime(target)
}"""
replacement = "\n".join(indent + line if line else "" for line in new.splitlines())
s = s[:matches[0].start()] + replacement + s[matches[0].end():]

if "open(uri, target, activeDigitalOutput)" not in s:
    raise SystemExit("Large-seek recovery verification failed; no source changed.")
p.write_text(s)
print("Large LibVLC seeks now reopen the current URI at the requested timestamp.")
