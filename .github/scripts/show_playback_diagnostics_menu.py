from pathlib import Path

p = Path("app/src/main/java/com/example/gx1player/MainActivity.kt")
s = p.read_text()
old = 'Triple("ⓘ", "Audio diagnostics", "audio_diagnostics"),'
new = 'Triple("ⓘ", "Playback Diagnostics", "audio_diagnostics"),'
if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    raise SystemExit("Could not find the existing diagnostics menu item; refusing to add a disconnected action")
if '"audio_diagnostics" -> showAudioDiagnostics()' not in s:
    raise SystemExit("Diagnostics menu action is missing")
if s.count(new) != 1:
    raise SystemExit("Playback Diagnostics menu item verification failed")
p.write_text(s)
print("Renamed the existing gear-menu item to the clear label Playback Diagnostics.")
