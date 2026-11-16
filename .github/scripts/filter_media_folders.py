from pathlib import Path
import re

p = Path("app/src/main/java/com/example/gx1player/MainActivity.kt")
s = p.read_text()

# The generated Kotlin is indented differently from the template. Match the
# two declarations independently of indentation and line-ending style.
s, n = re.subn(
    r'(?m)^[ \t]*val libraryMediaExt = videoExt \+ setOf\("mp3", "flac", "m4a", "aac", "wav", "ogg", "opus"\)[ \t]*\r?\n'
    r'[ \t]*val mediaExt = if \(selectingLibrary\) libraryMediaExt else videoExt[ \t]*$',
    '    val mediaExt = videoExt + setOf("mp3", "flac", "m4a", "aac", "wav", "ogg", "opus")',
    s,
    count=1,
)
if n == 0 and not re.search(r'(?m)^\s*val mediaExt = videoExt \+ setOf\("mp3", "flac", "m4a", "aac", "wav", "ogg", "opus"\)\s*$', s):
    raise SystemExit("Could not locate the GX1 supported-media extension declarations")

old_filter = r'\(f\.isDirectory\s*&&\s*\(selectingLibrary\s*\|\|\s*foldersOnly\s*\|\|\s*containsPlayableVideo\(f\)\)\)'
new_filter = '(f.isDirectory && !f.name.startsWith(".") && !f.name.equals("Android", true) && f.listFiles()?.any { child -> child.isFile && child.extension.lowercase() in mediaExt } == true)'
s, n = re.subn(old_filter, lambda _: new_filter, s, count=1)
if n == 0 and new_filter not in s:
    raise SystemExit("Could not find the expected GX1 folder filter")
if "containsPlayableVideo(f)" in s:
    raise SystemExit("Recursive folder scan is still active")
if 'val mediaExt = videoExt + setOf("mp3", "flac", "m4a", "aac", "wav", "ogg", "opus")' not in s or new_filter not in s:
    raise SystemExit("GX1 media-folder filter verification failed")

p.write_text(s)
print("GX1 browser now lists supported video/audio files and folders containing them directly; no recursive scan.")
