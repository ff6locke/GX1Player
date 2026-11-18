from pathlib import Path

root = Path("app/src/main/java/com/example/gx1player")
engine_path = root / "playback/Gx1LibVlcEngine.kt"
main_path = root / "MainActivity.kt"
if not engine_path.is_file() or not main_path.is_file():
    raise SystemExit("Generated LibVLC engine or MainActivity is missing")

engine = engine_path.read_text()
marker = "    private var attachedLayout: VLCVideoLayout? = null"
fields = r"""    private var attachedLayout: VLCVideoLayout? = null
    @Volatile private var lastVideoSurfaceSnapshot = "not captured"
    @Volatile private var lastNativeVideoState = "not queried"

    private fun queryNativeVideoState(): String {
        val names = listOf("getVoutCount", "getVideoTracksCount", "getVideoTrack", "getVideoTracks")
        return names.mapNotNull { name ->
            runCatching {
                val method = mediaPlayer.javaClass.methods.firstOrNull {
                    it.name == name && it.parameterCount == 0
                } ?: return@mapNotNull null
                val value = method.invoke(mediaPlayer)
                val rendered = when (value) {
                    is Array<*> -> value.joinToString(prefix = "[", postfix = "]") { track ->
                        if (track == null) "null" else {
                            val details = track.javaClass.methods
                                .filter { it.parameterCount == 0 && it.name in listOf("getId", "getName", "getType", "getCodec", "getWidth", "getHeight", "getFrameRateNum", "getFrameRateDen") }
                                .mapNotNull { method -> runCatching { method.name.removePrefix("get") + "=" + method.invoke(track) }.getOrNull() }
                            track.javaClass.simpleName + "(" + details.joinToString(",") + ")"
                        }
                    }
                    else -> value.toString()
                }
                "$name=$rendered"
            }.getOrNull()
        }.joinToString("; ").ifBlank { "No public zero-argument video-track/vout query available" }
    }

    private fun captureVideoSurfaceSnapshot(reason: String) {
        val layout = attachedLayout ?: return
        val lines = mutableListOf<String>()
        fun walk(view: android.view.View, depth: Int) {
            val prefix = " ".repeat(depth * 2)
            val detail = StringBuilder(
                "${view.javaClass.simpleName} ${view.width}x${view.height} " +
                    "visibility=${view.visibility} alpha=${view.alpha}"
            )
            when (view) {
                is android.view.SurfaceView -> detail.append(
                    " surfaceValid=${runCatching { view.holder.surface?.isValid }.getOrNull()}"
                )
                is android.view.TextureView -> detail.append(
                    " textureAvailable=${view.isAvailable} surfaceTexture=${view.surfaceTexture != null}"
                )
            }
            lines.add(prefix + detail)
            if (view is android.view.ViewGroup) {
                for (i in 0 until view.childCount) walk(view.getChildAt(i), depth + 1)
            }
        }
        walk(layout, 0)
        lastVideoSurfaceSnapshot = lines.joinToString("\n")
        lastNativeVideoState = queryNativeVideoState()
        android.util.Log.i(
            "GX1-VLC-SURFACE",
            "reason=$reason native=$lastNativeVideoState\n$lastVideoSurfaceSnapshot"
        )
    }

    fun surfaceDiagnosticsLines(): List<String> =
        listOf("LibVLC native video: $lastNativeVideoState") +
            lastVideoSurfaceSnapshot.split("\n").filter { it.isNotBlank() }
"""
if "fun surfaceDiagnosticsLines()" not in engine:
    if marker not in engine:
        raise SystemExit("Could not find attachedLayout field for diagnostics")
    engine = engine.replace(marker, fields, 1)

attach_old = """        mediaPlayer.attachViews(layout, null, true, false)
        attachedLayout = layout
"""
attach_new = """        mediaPlayer.attachViews(layout, null, true, false)
        attachedLayout = layout
        layout.addOnLayoutChangeListener { _, _, _, _, _, _, _, _, _ ->
            captureVideoSurfaceSnapshot("layout changed")
        }
        layout.post { captureVideoSurfaceSnapshot("attached and posted") }
"""
if attach_old in engine:
    engine = engine.replace(attach_old, attach_new, 1)
elif "captureVideoSurfaceSnapshot(\"attached and posted\")" not in engine:
    raise SystemExit("Could not find LibVLC attachViews call")

event_anchor = '            android.util.Log.i("GX1_FIRST_PLAY_TIMING",'
event_insert = """            lastNativeVideoState = queryNativeVideoState()
            if (event.type == MediaPlayer.Event.Vout ||
                event.type == MediaPlayer.Event.Playing ||
                event.type == MediaPlayer.Event.EncounteredError) {
                attachedLayout?.post { captureVideoSurfaceSnapshot("LibVLC event ${event.type}") }
            }
            android.util.Log.i("GX1-VLC-SURFACE", "event=${event.type} native=$lastNativeVideoState")
"""
if 'android.util.Log.i("GX1-VLC-SURFACE", "event=' not in engine:
    if event_anchor not in engine:
        raise SystemExit("Could not find LibVLC event logging insertion point")
    engine = engine.replace(event_anchor, event_insert + event_anchor, 1)

main_anchor = '        lines.addAll(mainVlcEngine?.startupTimingLines() ?: listOf("No active main LibVLC session"))'
main_insert = main_anchor + '\n        lines.addAll(mainVlcEngine?.surfaceDiagnosticsLines() ?: listOf("No active LibVLC surface snapshot"))'
main = main_path.read_text()
if "surfaceDiagnosticsLines()" not in main:
    if main_anchor not in main:
        raise SystemExit("Could not find startup diagnostics display in MainActivity")
    main = main.replace(main_anchor, main_insert, 1)
main_path.write_text(main)
engine_path.write_text(engine)

if "GX1-VLC-SURFACE" not in engine or "surfaceDiagnosticsLines()" not in main:
    raise SystemExit("LibVLC surface diagnostics verification failed")
print("Added LibVLC native video-track/vout and Android surface diagnostics; audio and passthrough paths were not modified.")
