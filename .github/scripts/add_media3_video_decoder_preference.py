from pathlib import Path

p = Path("app/src/main/java/com/example/gx1player/MainActivity.kt")
s = p.read_text()

imports = [
    "import androidx.media3.exoplayer.mediacodec.MediaCodecInfo",
    "import androidx.media3.exoplayer.mediacodec.MediaCodecSelector",
]
anchor = "import androidx.media3.exoplayer.DefaultRenderersFactory"
if anchor not in s:
    raise SystemExit("DefaultRenderersFactory import not found")
for imp in imports:
    if imp not in s:
        s = s.replace(anchor, anchor + "\n" + imp, 1)

class_anchor = "class MainActivity : AppCompatActivity() {"
annotated = "@androidx.media3.common.util.UnstableApi\n" + class_anchor
if annotated not in s:
    if class_anchor not in s:
        raise SystemExit("MainActivity class declaration not found")
    s = s.replace(class_anchor, annotated, 1)

factory_anchor = """        val renderers = if (passthrough) {
            TrueHdCarrierRenderersFactory(this)
        } else {
            PcmRenderersFactory(this)
        }
"""
factory_patch = factory_anchor + """
        // Apply the preference only to video codecs. Audio decoder ordering and
        // the existing passthrough/PCM renderer configuration remain unchanged.
        val videoDecoderPreference = prefs.getString("gx1_video_decoder_preference", "auto") ?: "auto"
        renderers.setMediaCodecSelector(object : MediaCodecSelector {
            override fun getDecoderInfos(
                mimeType: String,
                requiresSecureDecoder: Boolean,
                requiresTunnelingDecoder: Boolean
            ): List<MediaCodecInfo> {
                val decoders = MediaCodecSelector.DEFAULT.getDecoderInfos(
                    mimeType, requiresSecureDecoder, requiresTunnelingDecoder
                )
                if (!mimeType.startsWith("video/", ignoreCase = true)) return decoders
                val ordered = when (videoDecoderPreference.lowercase()) {
                    "hardware" -> decoders.sortedByDescending { it.hardwareAccelerated }
                    "software" -> decoders.sortedByDescending { it.softwareOnly }
                    else -> decoders
                }
                android.util.Log.i(
                    "GX1-VIDEO-DECODER",
                    "mime=$mimeType preference=$videoDecoderPreference order=" +
                        ordered.joinToString(",") { it.name }
                )
                return ordered
            }
        })
"""
if "GX1-VIDEO-DECODER" not in s:
    if s.count(factory_anchor) != 1:
        raise SystemExit(f"Expected one renderer factory block; found {s.count(factory_anchor)}")
    s = s.replace(factory_anchor, factory_patch, 1)

menu_anchor = """        add("Restart current video") {
"""
menu_patch = """        val decoderModes = arrayOf("Auto (default)", "Prefer hardware", "Prefer software")
        val decoderValues = arrayOf("auto", "hardware", "software")
        val savedDecoderMode = prefs.getString("gx1_video_decoder_preference", "auto") ?: "auto"
        val decoderIndex = decoderValues.indexOf(savedDecoderMode).coerceAtLeast(0)
        add("Video decoder: " + decoderModes[decoderIndex]) {
            AlertDialog.Builder(this)
                .setTitle("Video decoder preference")
                .setSingleChoiceItems(decoderModes, decoderIndex) { dialog, which ->
                    prefs.edit().putString("gx1_video_decoder_preference", decoderValues[which]).apply()
                    dialog.dismiss()
                    Toast.makeText(
                        this,
                        decoderModes[which] + " saved. Restart the video to apply.",
                        Toast.LENGTH_LONG
                    ).show()
                }
                .setNegativeButton("Close", null)
                .show()
        }
"""
if "Video decoder preference" not in s:
    if s.count(menu_anchor) != 1:
        raise SystemExit(f"Expected one playback menu insertion point; found {s.count(menu_anchor)}")
    s = s.replace(menu_anchor, menu_patch + menu_anchor, 1)

if "MediaCodecSelector.DEFAULT.getDecoderInfos" not in s or "GX1-VIDEO-DECODER" not in s:
    raise SystemExit("Media3 video decoder selector verification failed")
if 'prefs.edit().putString("gx1_video_decoder_preference"' not in s:
    raise SystemExit("Video decoder preference persistence verification failed")
p.write_text(s)
print("Added persisted Media3 video-only Auto/Prefer hardware/Prefer software decoder ordering. Audio codec selection and passthrough path are unchanged.")
