from pathlib import Path

p = Path("app/src/main/java/com/example/gx1player/MainActivity.kt")
s = p.read_text()
old_media = 'val libraryMediaExt = videoExt + setOf("mp3", "flac", "m4a", "aac", "wav", "ogg", "opus")\n              val mediaExt = if (selectingLibrary) libraryMediaExt else videoExt'
new_media = 'val mediaExt = videoExt + setOf("mp3", "flac", "m4a", "aac", "wav", "ogg", "opus")'
if old_media in s:
    s = s.replace(old_media, new_media, 1)
elif new_media not in s:
    raise SystemExit("Could not find the GX1 supported-media extension list")
old_filter = '(f.isDirectory && (selectingLibrary || foldersOnly || containsPlayableVideo(f)))'
new_filter = '(f.isDirectory && !f.name.startsWith(".") && !f.name.equals("Android", true) && f.listFiles()?.any { child -> child.isFile && child.extension.lowercase() in mediaExt } == true)'
if old_filter in s:
    s = s.replace(old_filter, new_filter, 1)
elif new_filter not in s:
    raise SystemExit("Could not find the expected GX1 folder filter")
if "containsPlayableVideo(f)" in s:
    raise SystemExit("Recursive folder scan is still active")
if new_media not in s or new_filter not in s:
    raise SystemExit("GX1 media-folder filter verification failed")
p.write_text(s)
print("GX1 browser now lists supported video/audio files and folders containing them directly; no recursive scan.")
