from pathlib import Path

p = Path("app/src/main/java/com/example/gx1player/MainActivity.kt")
s = p.read_text()

if "gx1ForceMedia3ForAac" in s or "isAacMultichannel" in s:
    raise SystemExit("AAC engine routing already exists; refusing duplicate patch")

field_anchor = "    private var mainVlcSelected = false"
if s.count(field_anchor) != 1:
    raise SystemExit("Could not locate unique playback-engine state")
s = s.replace(
    field_anchor,
    field_anchor + "\n    private var gx1ForceMedia3ForAac = false\n    private var gx1AacRouteGeneration = 0",
    1,
)

start_anchor = "    private fun startPlayer() {"
if s.count(start_anchor) != 1:
    raise SystemExit("Could not locate unique startPlayer method")

helper = """    private fun isAacMultichannel(uri: android.net.Uri): Boolean {
        val extractor = android.media.MediaExtractor()
        return try {
            extractor.setDataSource(this, uri, emptyMap())
            (0 until extractor.trackCount).any { index ->
                val format = extractor.getTrackFormat(index)
                val mime = format.getString(android.media.MediaFormat.KEY_MIME)
                val channels = if (format.containsKey(android.media.MediaFormat.KEY_CHANNEL_COUNT)) {
                    format.getInteger(android.media.MediaFormat.KEY_CHANNEL_COUNT)
                } else 0
                mime == "audio/mp4a-latm" && channels >= 6
            }.also { detected ->
                android.util.Log.i("GX1-AAC-ROUTE", "AAC multichannel detected=$detected uri=$uri")
            }
        } catch (e: Exception) {
            android.util.Log.w("GX1-AAC-ROUTE", "AAC detection failed; keeping LibVLC", e)
            false
        } finally {
            extractor.release()
        }
    }

"""
s = s.replace(start_anchor, helper + start_anchor, 1)

# Invalidate any outstanding background detection on every playback restart.
s = s.replace(start_anchor, start_anchor + "\n        gx1AacRouteGeneration++", 1)

old = """        if (mainVlcSelected) {
            startMainLibVlc(uri)
            return
        }"""
new = """        if (mainVlcSelected && !gx1ForceMedia3ForAac) {
            val routeGeneration = gx1AacRouteGeneration
            Thread({
                val useMedia3 = isAacMultichannel(uri)
                runOnUiThread {
                    if (routeGeneration != gx1AacRouteGeneration || mediaUri != uri || !mainVlcSelected) {
                        return@runOnUiThread
                    }
                    if (useMedia3) {
                        android.util.Log.i("GX1-AAC-ROUTE", "Using Media3 for multichannel AAC; LibVLC remains the saved default")
                        gx1ForceMedia3ForAac = true
                        try {
                            startPlayer()
                        } finally {
                            gx1ForceMedia3ForAac = false
                        }
                    } else {
                        startMainLibVlc(uri)
                    }
                }
            }, "gx1-aac-engine-detect").apply {
                isDaemon = true
                start()
            }
            return
        }"""
if old not in s:
    raise SystemExit("Expected LibVLC default-engine branch not found exactly")
s = s.replace(old, new, 1)

p.write_text(s)
print("Added background AAC multichannel detection: AAC >= 6 channels uses Media3; all other media remains on LibVLC.")
