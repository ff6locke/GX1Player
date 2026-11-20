from pathlib import Path
import re

p = Path("app/src/main/java/com/example/gx1player/MainActivity.kt")
s = p.read_text()

# Media3's default fade leaves custom controls visually detached from the
# seek bar. Disable that animation so the entire controller is one unit.
anchor = "        setContentView(root)"
if anchor not in s:
    raise SystemExit("Could not find root installation point")
setup = """        playerView.findViewById<androidx.media3.ui.PlayerControlView>(
            androidx.media3.ui.R.id.exo_controller
        )?.apply {
            setAnimationEnabled(false)
            setShowTimeoutMs(2500)
        }
        playerView.controllerAutoShow = false
        playerView.controllerHideOnTouch = true
        playerView.hideController()
"""
if "setAnimationEnabled(false)" not in s:
    s = s.replace(anchor, setup + anchor, 1)

# Do not explicitly reopen the controls after switching to an adjacent file.
pattern = re.compile(r"(private fun playAdjacentGx1File\(direction: Int\) \{.*?selectMedia\(target\)\s*startPlayer\(\))\s*playerView\.showController\(\)", re.S)
s, n = pattern.subn(r"\1\n        playerView.hideController()", s, count=1)
if n != 1:
    raise SystemExit(f"Could not patch adjacent-file overlay behavior: {n}")

# Every fresh Media3 item starts with a clean controller, even if prepare/play
# causes Media3 to request an automatic controller display.
for marker in ["        playerView.player = exo", "        exo.prepare()"]:
    if marker not in s:
        raise SystemExit("Missing playback-start anchor: " + marker)
    line = marker + "\n        playerView.hideController()"
    if line not in s:
        s = s.replace(marker, line, 1)

# Keep the custom previous/next controls synchronized with the Media3
# controller visibility callback. With animations disabled they transition
# in the same frame as the seek bar and transport bar.
callback_anchor = "override fun onVisibilityChanged(visibility: Int) {"
pos = s.find(callback_anchor)
if pos < 0:
    raise SystemExit("Controller visibility callback missing")
end = s.find("\n", pos)
sync = """
                              gx1PreviousFileButton?.visibility = visibility
                              gx1NextFileButton?.visibility = visibility
"""
if "gx1PreviousFileButton?.visibility = visibility" not in s:
    s = s[:end+1] + sync + s[end+1:]

p.write_text(s)
print("Playback overlay now uses an immediate, non-animated Media3 controller; new items start hidden and file navigation controls follow controller visibility.")
