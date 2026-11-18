from pathlib import Path
import re

root = Path("app/src/main/java")
engines = list(root.rglob("Gx1LibVlcEngine.kt"))
if len(engines) != 1:
    raise SystemExit(f"Expected exactly one Gx1LibVlcEngine.kt after LibVLC generation; found {len(engines)}")
engine_path = engines[0]
engine = engine_path.read_text()

old_ctor = """    context: Context,
    private val onStateChanged: (State) -> Unit = {}
) {"""
new_ctor = """    context: Context,
    private val decoderMode: String = "auto",
    private val onStateChanged: (State) -> Unit = {}
) {"""
if old_ctor in engine:
    engine = engine.replace(old_ctor, new_ctor, 1)
elif new_ctor not in engine:
    raise SystemExit("Could not locate LibVLC engine constructor")

diagnostic = re.compile(
    r"\s*// Diagnostic only: software decode the reported 4K AVC sample\.\s*"
    r"if \(uri\.lastPathSegment\?\.contains\(\"sample_3840x2160\", ignoreCase = true\) == true\) \{\s*"
    r"media\.addOption\(\":avcodec-hw=none\"\)\s*"
    r"android\.util\.Log\.w\(\"GX1-VLC\", \"Diagnostic software decoding enabled for sample_3840x2160\"\)\s*"
    r"\}\s*",
    re.S
)
engine, removed = diagnostic.subn("\n", engine, count=1)
if removed != 1 and "Diagnostic only: software decode" in engine:
    raise SystemExit("Could not safely remove filename-specific decoder diagnostic")

decoder_block = """        when (decoderMode.trim().lowercase()) {
            "hardware" -> {
                media.addOption(":avcodec-hw=any")
                android.util.Log.i("GX1-VLC", "Video decoder mode=Hardware")
            }
            "software" -> {
                media.addOption(":avcodec-hw=none")
                android.util.Log.i("GX1-VLC", "Video decoder mode=Software")
            }
            else -> {
                android.util.Log.i("GX1-VLC", "Video decoder mode=Auto (LibVLC default)")
            }
        }
"""
anchor = "            mediaPlayer.media = media"
if decoder_block.strip() not in engine:
    if anchor not in engine:
        raise SystemExit("Could not find media creation point for decoder option")
    engine = engine.replace(anchor, decoder_block + anchor, 1)
engine_path.write_text(engine)

main_path = root / "com/example/gx1player/MainActivity.kt"
if not main_path.is_file():
    candidates = list(root.rglob("MainActivity.kt"))
    if len(candidates) != 1:
        raise SystemExit(f"Expected one MainActivity.kt; found {len(candidates)}")
    main_path = candidates[0]
main = main_path.read_text()
old_call = "val engine = Gx1LibVlcEngine(this) { state -> runOnUiThread {"
new_call = 'val engine = Gx1LibVlcEngine(this, decoderMode = prefs.getString("gx1_decoder_mode", "auto") ?: "auto") { state -> runOnUiThread {'
if old_call in main:
    main = main.replace(old_call, new_call, 1)
elif new_call not in main:
    raise SystemExit("Could not locate main LibVLC engine creation call")

menu_anchor = '        add("Built-in subtitle tracks") { showSubtitleTrackSelection() }'
menu_item = r'''        add("LibVLC video decoder: " + (prefs.getString("gx1_decoder_mode", "auto") ?: "auto").replaceFirstChar { it.uppercase() }) {
            val modes = arrayOf("Auto", "Hardware", "Software")
            val values = arrayOf("auto", "hardware", "software")
            val current = prefs.getString("gx1_decoder_mode", "auto") ?: "auto"
            val selected = values.indexOf(current.lowercase()).coerceAtLeast(0)
            AlertDialog.Builder(this)
                .setTitle("LibVLC video decoder")
                .setSingleChoiceItems(modes, selected) { dialog, which ->
                    prefs.edit().putString("gx1_decoder_mode", values[which]).apply()
                    dialog.dismiss()
                    Toast.makeText(this, "Decoder set to " + modes[which] + ". Restart the current video to apply.", Toast.LENGTH_LONG).show()
                }
                .setNegativeButton("Close", null)
                .show()
        }
'''
if menu_item.strip() not in main:
    if menu_anchor not in main:
        raise SystemExit("Could not find playback menu insertion point")
    main = main.replace(menu_anchor, menu_item + menu_anchor, 1)
main_path.write_text(main)

if "sample_3840x2160" in engine:
    raise SystemExit("Filename-specific decoder diagnostic remains")
if 'prefs.getString("gx1_decoder_mode"' not in main or "LibVLC video decoder" not in main:
    raise SystemExit("Decoder selector verification failed")
print("LibVLC Auto/Hardware/Software selector verified. Audio passthrough code was not changed.")
