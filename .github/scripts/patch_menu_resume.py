from pathlib import Path
import re
p = Path("app/src/main/java/com/example/gx1player/MainActivity.kt")
s = p.read_text()
for imp in ["import androidx.activity.OnBackPressedCallback", "import androidx.media3.common.PlaybackException"]:
    if imp not in s:
        s = s.replace("import androidx.activity.result.contract.ActivityResultContracts", imp + "\n" + "import androidx.activity.result.contract.ActivityResultContracts", 1)
s = s.replace('arrayOf("video/*", "audio/*")', 'arrayOf("video/*", "audio/*", "application/octet-stream", "application/x-matroska")')
s = s.replace(
    'val builder = MediaItem.Builder().setUri(uri)',
    '''val builder = MediaItem.Builder().setUri(uri)
        if (displayName(uri).endsWith(".mkv", ignoreCase = true)) {
            builder.setMimeType(MimeTypes.APPLICATION_MATROSKA)
        }''', 1)
s = s.replace(
    '                if (!isPlaying) savePosition(exo)\n            }',
    '''                if (!isPlaying) savePosition(exo)
    }
    override fun onPlayerError(error: PlaybackException) {
        val causes = generateSequence<Throwable>(error) { it.cause }
            .take(6)
            .map { cause -> "${cause.javaClass.simpleName}: ${cause.message ?: "no message"}" }
            .joinToString(" <- ")
        val detail = "${error.errorCodeName} | $causes"
        android.util.Log.e("GX1Player", "Media3 playback failed: $detail", error)
        runOnUiThread {
            AlertDialog.Builder(this@MainActivity)
                .setTitle("Playback error")
                .setMessage(detail + "\n\nSelected: " + (mediaUri?.toString() ?: "unknown"))
                .setPositiveButton("OK", null)
                .show()
        }
    }''', 1)
startup_line = '        val initial = intent?.data ?: prefs.getString(KEY_LAST_URI, null)?.let { Uri.parse(it) }'
if startup_line not in s:
    raise SystemExit("Could not find startup media restore line")
s = s.replace(startup_line, '        val initial: Uri? = null', 1)
back_marker = '        val initial: Uri? = null'
back_callback = '''        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
    override fun handleOnBackPressed() {
        showMenu()
    }
})
'''
if 'onBackPressedDispatcher.addCallback(this' not in s:
    if back_marker not in s:
        raise SystemExit("Could not find onCreate insertion point for Back handling")
    s = s.replace(back_marker, back_callback + back_marker, 1)
for imp in ["import android.view.Gravity", "import android.widget.Button", "import android.widget.FrameLayout"]:
    if imp not in s:
        s = s.replace("import android.view.KeyEvent", "import android.view.KeyEvent\n" + imp, 1)
if "setContentView(playerView)" in s and 'text = "Menu"' not in s:
    s = s.replace(
        "        setContentView(playerView)",
        """        val root = FrameLayout(this)
        rootLayout = root
        playerView.subtitleView?.setStyle(
            androidx.media3.ui.CaptionStyleCompat(
                Color.WHITE, Color.TRANSPARENT, Color.TRANSPARENT,
                androidx.media3.ui.CaptionStyleCompat.EDGE_TYPE_NONE,
                Color.TRANSPARENT, null
            )
        )
        root.addView(playerView, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ))
        val playbackTitle = android.widget.TextView(this).apply {
            tag = "gx1_playback_title"
            setTextColor(Color.WHITE)
            textSize = 16f
            typeface = android.graphics.Typeface.DEFAULT_BOLD
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.MIDDLE
            gravity = Gravity.CENTER
            setPadding(18, 8, 18, 8)
            background = android.graphics.drawable.GradientDrawable().apply {
                setColor(0x99000000.toInt())
                cornerRadius = 10f
            }
            visibility = android.view.View.GONE
        }
        val playbackOverlay = playerView.findViewById<FrameLayout>(
            androidx.media3.ui.R.id.exo_overlay
        )
        playbackOverlay?.addView(playbackTitle, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.WRAP_CONTENT,
            FrameLayout.LayoutParams.WRAP_CONTENT,
            Gravity.TOP or Gravity.CENTER_HORIZONTAL
        ).apply { topMargin = (18 * resources.displayMetrics.density).toInt() })
        if (playbackOverlay == null) {
            android.util.Log.e("GX1Player", "Media3 exo_overlay was not found; playback title cannot be displayed")
        }
        homePanel = buildHomePanel()
        root.addView(homePanel, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ))
        playerView.visibility = android.view.View.GONE
        val media3SettingsGear = playerView.findViewById<android.view.View>(
            androidx.media3.ui.R.id.exo_settings
        )
        media3SettingsGear?.apply {
            visibility = android.view.View.VISIBLE
            setOnClickListener { showMenu() }
            contentDescription = "Playback settings"
        }
        media3SettingsGear?.let { gear ->
            val gearParent = gear.parent as? android.view.ViewGroup
            if (gearParent != null && gearParent.findViewWithTag<android.view.View>("gx1_open_video") == null) {
                val gearIndex = gearParent.indexOfChild(gear)
                val openVideoButton = android.widget.ImageButton(this).apply {
                    tag = "gx1_open_video"
                    setImageDrawable(object : android.graphics.drawable.Drawable() {
                        private val folderPaint = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply {
                            color = Color.WHITE
                            style = android.graphics.Paint.Style.FILL
                        }
                        private val videoPaint = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply {
                            color = Color.rgb(20, 91, 245)
                            style = android.graphics.Paint.Style.FILL
                        }
                        private val detailPaint = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply {
                            color = Color.WHITE
                            style = android.graphics.Paint.Style.FILL
                        }
                        override fun draw(canvas: android.graphics.Canvas) {
                            val b = bounds
                            canvas.save()
                            canvas.translate(b.left.toFloat(), b.top.toFloat())
                            canvas.scale(b.width() / 24f, b.height() / 24f)
                            val folder = android.graphics.Path().apply {
                                moveTo(2f, 6f); quadTo(2f, 4f, 4f, 4f)
                                lineTo(9f, 4f); lineTo(11f, 6.5f); lineTo(20f, 6.5f)
                                quadTo(22f, 6.5f, 22f, 8.5f); lineTo(22f, 18.5f)
                                quadTo(22f, 21f, 19.5f, 21f); lineTo(4.5f, 21f)
                                quadTo(2f, 21f, 2f, 18.5f); close()
                            }
                            canvas.drawPath(folder, folderPaint)
                            val film = android.graphics.RectF(6f, 8f, 18.5f, 18.5f)
                            canvas.drawRoundRect(film, 1.5f, 1.5f, videoPaint)
                            for (y in listOf(9.5f, 12f, 14.5f, 17f)) {
                                canvas.drawRoundRect(7f, y, 8.2f, y + 1.1f, 0.3f, 0.3f, detailPaint)
                                canvas.drawRoundRect(16.3f, y, 17.5f, y + 1.1f, 0.3f, 0.3f, detailPaint)
                            }
                            val play = android.graphics.Path().apply {
                                moveTo(10f, 10.5f); lineTo(15f, 13.25f); lineTo(10f, 16f); close()
                            }
                            canvas.drawPath(play, detailPaint)
                            canvas.restore()
                        }
                        override fun setAlpha(alpha: Int) {
                            folderPaint.alpha = alpha; videoPaint.alpha = alpha; detailPaint.alpha = alpha
                        }
                        override fun setColorFilter(filter: android.graphics.ColorFilter?) {
                            folderPaint.colorFilter = filter; videoPaint.colorFilter = filter; detailPaint.colorFilter = filter
                        }
                        @Deprecated("Deprecated in Java")
                        override fun getOpacity(): Int = android.graphics.PixelFormat.TRANSLUCENT
                        override fun getIntrinsicWidth(): Int = 24
                        override fun getIntrinsicHeight(): Int = 24
                    })
                    background = android.graphics.drawable.ColorDrawable(Color.TRANSPARENT)
                    contentDescription = "Open video"
                    isFocusable = true
                    isClickable = true
                    setPadding(0, 0, 0, 0)
                    scaleType = android.widget.ImageView.ScaleType.FIT_CENTER
                    setOnClickListener {
                        chooseLibraryLocation()
                    }
                }
                val oldParams = gear.layoutParams
                val buttonParams: android.view.ViewGroup.LayoutParams = when (oldParams) {
                    is android.widget.LinearLayout.LayoutParams -> android.widget.LinearLayout.LayoutParams(oldParams)
                    is android.widget.FrameLayout.LayoutParams -> android.widget.FrameLayout.LayoutParams(oldParams)
                    else -> android.view.ViewGroup.LayoutParams(oldParams)
                }
                gearParent.addView(openVideoButton, gearIndex, buttonParams)
            }
        }
        val menuButton = Button(this).apply {
            text = "\u2699\uFE0E"
            textSize = 36f
            typeface = android.graphics.Typeface.create("sans-serif", android.graphics.Typeface.NORMAL)
            isAllCaps = false
            setTextColor(Color.WHITE)
            alpha = 1f
            contentDescription = "Open playback menu"
            minWidth = 0
            minHeight = 0
            setPadding(0, 0, 0, 3)
            background = GradientDrawable().apply {
                shape = GradientDrawable.OVAL
                setColor(Color.rgb(28, 34, 46))
                setStroke(2, Color.rgb(150, 177, 210))
            }
            elevation = 12f
            setOnFocusChangeListener { v, focused ->
                v.background = GradientDrawable().apply {
                    shape = GradientDrawable.OVAL
                    setColor(if (focused) Color.rgb(73, 48, 25) else Color.rgb(28, 34, 46))
                    setStroke(if (focused) 4 else 2,
                        if (focused) Color.rgb(255, 152, 0) else Color.rgb(150, 177, 210))
                }
            }
            setOnClickListener { showMenu() }
            visibility = android.view.View.GONE
        }
        val menuParams = FrameLayout.LayoutParams(
            72,
            72,
            Gravity.BOTTOM or Gravity.END
        ).apply { setMargins(0, 0, 30, 30) }
        menuButtonRef = menuButton
        menuButton.visibility = android.view.View.GONE
        setContentView(root)""",
        1
    )
if 'add("Resume last video")' not in s:
    s, n = re.subn(
        r'    private fun selectMedia\(uri: Uri\) \{.*?\n    \}',
        '''    private fun selectMedia(uri: Uri) {
        mediaUri = uri
        if (::rootLayout.isInitialized) {
            rootLayout.findViewWithTag<android.widget.TextView>("gx1_playback_title")?.apply {
                text = displayName(uri)
                visibility = android.view.View.VISIBLE
            }
        }
        prefs.edit().putString(KEY_LAST_URI, uri.toString()).apply()
        subtitleUri = prefs.getString(subKey(uri), null)?.let { Uri.parse(it) }
    }''',
        s, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("Could not patch selectMedia()")
if "override fun onPositionDiscontinuity(" not in s:
    marker = "        exo.addAnalyticsListener(object : AnalyticsListener {"
    listener = """        // Persist resume position immediately on pause, seek, and playback-state changes.
        exo.addListener(object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                if (!isPlaying) savePosition(exo)
            }                      override fun onPlaybackStateChanged(playbackState: Int) {
                if (playbackState == Player.STATE_ENDED || playbackState == Player.STATE_READY) {
                    savePosition(exo)
                }
            }
            override fun onPositionDiscontinuity(
                oldPosition: Player.PositionInfo,
                newPosition: Player.PositionInfo,
                reason: Int
            ) {
                savePosition(exo)
            }
            override fun onVideoSizeChanged(videoSize: androidx.media3.common.VideoSize) = applyMedia3AspectMode()
        })
"""
    if marker not in s:
        raise SystemExit("Could not find player listener insertion point")
    s = s.replace(marker, listener + marker, 1)
if 'add("Resume last video")' not in s:
    marker = '        add("Open video file") { pickVideo.launch(arrayOf("video/*", "audio/*")) }'
    resume = """        add("Resume last video") {
            val last = prefs.getString(KEY_LAST_URI, null)?.let { Uri.parse(it) }
            if (last != null) {
                selectMedia(last)
                startPlayer()
            } else {
                Toast.makeText(this, "No previous video", Toast.LENGTH_SHORT).show()
            }
        }
"""
    if marker not in s:
        raise SystemExit("Could not find Open video menu item")
    s = s.replace(marker, marker + "\n" + resume, 1)
if 'add("Restart current video")' not in s:
    marker = '        add(if (passthrough) "Audio pass-through: On (select to turn off)" else "Audio pass-through: Off (select to turn on)") {'
    restart = """        add("Restart current video") {
            mediaUri?.let { uri ->
                prefs.edit().remove(posKey(uri)).apply()
                startPlayer()
            }
        }
"""
    if marker not in s:
        raise SystemExit("Could not find audio menu item")
    s = s.replace(marker, restart + marker, 1)
s = s.replace('        private const val KEY_SUBS_ON = "subs_on"',
              '        private const val KEY_SUBS_ON = "subs_on"\n        private const val KEY_HISTORY_PREFIX = "history|"')
s = s.replace('    private var subtitleUri: Uri? = null     // external subtitle file for mediaUri',
              '    private var subtitleUri: Uri? = null     // first external subtitle\n    private var subtitleUri2: Uri? = null    // second external subtitle\n    private fun subKey(uri: Uri) = KEY_SUBTITLE_1 + uri.toString()')
second_picker = """
private val pickSubtitle2 = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
    if (uri == null) return@registerForActivityResult
    takePermission(uri)
    subtitleUri2 = uri
    mediaUri?.let { prefs.edit().putString(subKey(it) + "|2", uri.toString()).apply() }
    loadSecondSubtitleOverlay(uri)
}
"""
if "private val pickSubtitle2" not in s:
    s = s.replace('    override fun onCreate(savedInstanceState: Bundle?) {', second_picker + '\n    override fun onCreate(savedInstanceState: Bundle?) {', 1)
s = s.replace('        subtitleUri = prefs.getString(subKey(uri), null)?.let { Uri.parse(it) }',
              '        subtitleUri = prefs.getString(subKey(uri), null)?.let { Uri.parse(it) }\n        subtitleUri2 = prefs.getString(subKey(uri) + "|2", null)?.let { Uri.parse(it) }')
old_subs = """        subtitleUri?.let { sub ->
    val name = displayName(sub)
    builder.setSubtitleConfigurations(
        listOf(
            MediaItem.SubtitleConfiguration.Builder(sub)
                .setMimeType(subtitleMime(name))
                .setLabel(name)
                .setSelectionFlags(C.SELECTION_FLAG_DEFAULT)
                .build()
        )
    )
}"""
new_subs = """        val subtitleConfigs = listOfNotNull(subtitleUri, subtitleUri2).mapIndexed { index, sub ->
    val name = displayName(sub)
    MediaItem.SubtitleConfiguration.Builder(sub)
        .setMimeType(subtitleMime(name))
        .setLabel(name)
        .setSelectionFlags(if (index == 0) C.SELECTION_FLAG_DEFAULT else 0)
        .build()
}
if (subtitleConfigs.isNotEmpty()) builder.setSubtitleConfigurations(subtitleConfigs)"""
if old_subs in s:
    s = s.replace(old_subs, new_subs, 1)
s = s.replace('        subtitleUri = null\n        mediaUri?.let { prefs.edit().remove(subKey(it)).apply() }',
              '        subtitleUri = null\n        subtitleUri2 = null\n        mediaUri?.let { prefs.edit().remove(subKey(it)).remove(subKey(it) + "|2").apply() }')
s = s.replace('        add("Load subtitle file") {\n            pickSubtitle.launch(arrayOf("application/x-subrip", "text/vtt", "text/plain", "application/octet-stream"))\n        }',
              '        add("Load subtitle 1") { pickSubtitle.launch(arrayOf("application/x-subrip", "text/vtt", "text/plain", "application/octet-stream")) }\n        add("Load subtitle 2") { pickSubtitle2.launch(arrayOf("application/x-subrip", "text/vtt", "text/plain", "application/octet-stream")) }')
s = s.replace('        if (subtitleUri != null) add("Remove external subtitle") { removeExternalSubtitle() }',
              '        if (subtitleUri != null || subtitleUri2 != null) add("Remove external subtitles") { removeExternalSubtitle() }')
s = s.replace('        add("Build info") { showBuildInfo() }',
              '        add("History") { showHistory() }\n        add("Build info") { showBuildInfo() }')
history_method = """
private fun showHistory() {
    val entries = prefs.all.entries
        .filter { it.key.startsWith(KEY_HISTORY_PREFIX) && it.value is Long }
        .sortedByDescending { it.value as Long }
        .mapNotNull { runCatching { Uri.parse(it.key.removePrefix(KEY_HISTORY_PREFIX)) }.getOrNull() }
    if (entries.isEmpty()) {
        Toast.makeText(this, "No playback history yet", Toast.LENGTH_SHORT).show()
        return
    }
    AlertDialog.Builder(this)
        .setTitle("History")
        .setItems(entries.map { displayName(it) }.toTypedArray()) { _, which ->
            selectMedia(entries[which])
            startPlayer()
        }
        .setNegativeButton("Close", null)
        .show()
}
"""
if "private fun showHistory()" not in s:
    s = s.replace('    private fun togglePassthrough() {', history_method + '    private fun togglePassthrough() {', 1)
s = s.replace('        prefs.edit().putString(KEY_LAST_URI, uri.toString()).apply()\n        subtitleUri =',
              '        prefs.edit().putString(KEY_LAST_URI, uri.toString()).putLong(KEY_HISTORY_PREFIX + uri.toString(), System.currentTimeMillis()).apply()\n        subtitleUri =')
for imp in ["import android.provider.DocumentsContract", "import android.database.Cursor"]:
    if imp not in s:
        s = s.replace("import android.net.Uri", "import android.net.Uri\n" + imp, 1)
for imp in ["import android.Manifest", "import android.content.pm.PackageManager", "import android.os.Build", "import android.provider.MediaStore", "import android.content.ContentUris"]:
    if imp not in s:
        s = s.replace("import android.net.Uri", "import android.net.Uri\n" + imp, 1)
manifest = Path("app/src/main/AndroidManifest.xml")
ms = manifest.read_text()
perms = """    <uses-permission android:name="android.permission.READ_MEDIA_VIDEO" />
    <uses-permission android:name="android.permission.READ_MEDIA_AUDIO" />
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32" />
    <uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" />
"""
if "android.permission.READ_MEDIA_VIDEO" not in ms:
    ms = ms.replace("<application", perms + "\n    <application", 1)
    manifest.write_text(ms)
library_launcher = r'''
private val libraryPermissionRequest = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
    if (result.values.any { it }) showLibrary("") else Toast.makeText(this, "Media access is needed to browse internal storage.", Toast.LENGTH_LONG).show()
}
private val chooseSdCardTree = registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
    if (uri != null) {
        try {
            contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        } catch (_: Exception) {
            try { contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) } catch (_: Exception) {}
        }
        prefs.edit().putString("library_tree_uri", uri.toString()).apply()
        showGX1Library()
    }
}
private fun chooseLibraryLocation() {
    AlertDialog.Builder(this)
        .setTitle("Choose storage")
        .setItems(arrayOf("Internal storage", "External SD card")) { _, which ->
            if (which == 0) {
                val permissions = if (Build.VERSION.SDK_INT >= 33) arrayOf(Manifest.permission.READ_MEDIA_VIDEO, Manifest.permission.READ_MEDIA_AUDIO)
                    else arrayOf(Manifest.permission.READ_EXTERNAL_STORAGE)
                val missing = permissions.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
                if (missing.isEmpty()) showLibrary("") else libraryPermissionRequest.launch(missing.toTypedArray())
            } else {
                browseExternalSdCard()
            }
        }
        .setNegativeButton("Cancel", null)
        .show()
}
private fun browseExternalSdCard(path: java.io.File? = null) {
    if (Build.VERSION.SDK_INT >= 30 && !Environment.isExternalStorageManager()) {
        try {
            val intent = Intent(android.provider.Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                Uri.parse("package:" + packageName))
            startActivity(intent)
        } catch (_: Exception) {
            startActivity(Intent(android.provider.Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION))
        }
        Toast.makeText(this, "Allow GX1 Player file access, then open External SD card again.", Toast.LENGTH_LONG).show()
        return
    }
    val roots = getExternalFilesDirs(null).filterNotNull().mapNotNull { dir ->
        val p = dir.absolutePath
        val marker = "/Android/data/"
        val cut = p.indexOf(marker)
        if (cut > 0) java.io.File(p.substring(0, cut)) else null
    }.distinctBy { it.absolutePath }
    val sdRoot = roots.firstOrNull { it.absolutePath != Environment.getExternalStorageDirectory().absolutePath }
    if (sdRoot == null || !sdRoot.exists()) {
        AlertDialog.Builder(this).setTitle("External SD card")
            .setMessage("No removable SD card was detected. Insert or mount the card and try again.")
            .setPositiveButton("OK", null).show()
        return
    }
    val current = path ?: sdRoot
    val entries = current.listFiles()?.filter { it.isDirectory || it.isFile &&
        it.extension.lowercase() in listOf("mkv","mp4","avi","mov","webm","mpg","mpeg","ts","m2ts","mp3","flac","m4a","aac","wav","ogg") }
        ?.sortedWith(compareBy<java.io.File>({ !it.isDirectory }, { it.name.lowercase() })) ?: emptyList()
    val labels = mutableListOf<String>()
    if (current.absolutePath != sdRoot.absolutePath) labels.add("..")
    entries.forEach { labels.add(if (it.isDirectory) "📁 " + it.name else "▶ " + it.name) }
    if (labels.isEmpty()) labels.add("(No media files or folders)")
    val relative = current.relativeTo(sdRoot).path.let { if (it == ".") "" else it }
    AlertDialog.Builder(this).setTitle("SD card / " + relative)
        .setItems(labels.toTypedArray()) { _, which ->
            if (current.absolutePath != sdRoot.absolutePath && which == 0) {
                browseExternalSdCard(current.parentFile ?: sdRoot)
            } else {
                val index = which - if (current.absolutePath != sdRoot.absolutePath) 1 else 0
                if (index in entries.indices) {
                    val selected = entries[index]
                    if (selected.isDirectory) browseExternalSdCard(selected)
                    else {
                        selectMedia(Uri.fromFile(selected))
                        startPlayer()
                    }
                }
            }
        }
        .setNegativeButton("Close", null)
        .setNeutralButton("Refresh") { _, _ -> browseExternalSdCard(current) }
        .show()
}
'''
if "private val libraryPermissionRequest" not in s:
    s = s.replace("    override fun onCreate(savedInstanceState: Bundle?) {", library_launcher + "\n    override fun onCreate(savedInstanceState: Bundle?) {", 1)
library_methods = r'''
private fun showLibrary(path: String = "") {
    data class Entry(val label: String, val folder: String? = null, val uri: Uri? = null)
    val folders = sortedSetOf<String>(String.CASE_INSENSITIVE_ORDER)
    val files = mutableListOf<Entry>()
    val collection = MediaStore.Files.getContentUri("external")
    val projection = arrayOf(MediaStore.MediaColumns._ID, MediaStore.MediaColumns.DISPLAY_NAME, MediaStore.MediaColumns.RELATIVE_PATH, MediaStore.MediaColumns.MIME_TYPE)
    try {
        contentResolver.query(collection, projection, null, null, MediaStore.MediaColumns.DISPLAY_NAME + " COLLATE NOCASE ASC")?.use { cursor ->
            val idCol = cursor.getColumnIndexOrThrow(MediaStore.MediaColumns._ID)
            val nameCol = cursor.getColumnIndexOrThrow(MediaStore.MediaColumns.DISPLAY_NAME)
            val pathCol = cursor.getColumnIndexOrThrow(MediaStore.MediaColumns.RELATIVE_PATH)
            val mimeCol = cursor.getColumnIndexOrThrow(MediaStore.MediaColumns.MIME_TYPE)
            while (cursor.moveToNext()) {
                val mime = cursor.getString(mimeCol) ?: continue
                if (!mime.startsWith("video/") && !mime.startsWith("audio/")) continue
                val relative = (cursor.getString(pathCol) ?: "").trimStart(47.toChar())
                if (!relative.startsWith(path, ignoreCase = true)) continue
                val remainder = relative.substring(path.length)
                val slash = remainder.indexOf(47.toChar())
                if (slash >= 0) {
                    val folder = remainder.substring(0, slash)
                    if (folder.isNotBlank()) folders.add(folder)
                } else {
                    val id = cursor.getLong(idCol)
                    val name = cursor.getString(nameCol) ?: continue
                    files.add(Entry(name, uri = ContentUris.withAppendedId(collection, id)))
                }
            }
        }
    } catch (e: Exception) {
        Toast.makeText(this, "Cannot read media storage: ${e.message}", Toast.LENGTH_LONG).show()
        return
    }
    val entries = mutableListOf<Entry>()
    if (path.isNotEmpty()) entries.add(Entry("..  Parent folder", folder = ".."))
    folders.forEach { entries.add(Entry("📁  " + it, folder = it)) }
    entries.addAll(files)
    if (entries.isEmpty()) entries.add(Entry("No video or audio files in this folder"))
    val title = if (path.isEmpty()) "GX1 PLAYER  ·  LIBRARY" else "LIBRARY  ·  " + path.trimEnd(47.toChar())
    AlertDialog.Builder(this).setTitle(title).setItems(entries.map { it.label }.toTypedArray()) { _, which ->
        val item = entries[which]
        when {
            item.folder == ".." -> { val current = path.trimEnd(47.toChar()); val parent = current.substringBeforeLast(47.toChar(), ""); showLibrary(if (parent.isEmpty()) "" else "$parent/") }
            item.folder != null -> showLibrary(path + item.folder + "/")
            item.uri != null -> { selectMedia(item.uri); startPlayer() }
        }
    }.setPositiveButton("Close", null).setNeutralButton("Refresh") { _, _ -> showLibrary(path) }.show()
}
'''
if "private fun showLibrary(path: String = \"\")" not in s:
    s = s.replace("    private fun showMenu() {", library_methods + "    private fun showMenu() {", 1)
if 'addTile("Library"' not in s:
    s = s.replace('              addTile("Open video", "Browse files") {',
                  '              addTile("Library", "Browse your folders") { chooseLibraryLocation() }\n              addTile("Open video", "Choose one file") {', 1)
for imp in ["import android.graphics.drawable.GradientDrawable", "import android.view.View", "import android.widget.LinearLayout", "import android.widget.TextView"]:
    if imp not in s:
        s = s.replace("import android.view.KeyEvent", "import android.view.KeyEvent\n" + imp, 1)
if "private lateinit var rootLayout: FrameLayout" not in s:
    s = s.replace("    private lateinit var playerView: PlayerView", "    private lateinit var playerView: PlayerView", 1)
home_methods = r'''
private fun buildHomePanel(): LinearLayout {
    val panel = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(56, 36, 56, 32)
        setBackgroundColor(Color.rgb(10, 14, 22))
        gravity = android.view.Gravity.CENTER_VERTICAL
    }
    val brand = TextView(this).apply {
        text = "GX1 PLAYER"
        textSize = 30f
        setTextColor(Color.WHITE)
        letterSpacing = 0.12f
        setTypeface(null, android.graphics.Typeface.BOLD)
    }
    panel.addView(brand)
    val subtitle = TextView(this).apply {
        text = "Your movies. Your screen."
        textSize = 16f
        setTextColor(Color.LTGRAY)
        setPadding(0, 6, 0, 28)
    }
    panel.addView(subtitle)
    val section = TextView(this).apply {
        text = "LIBRARY"
        textSize = 13f
        letterSpacing = 0.18f
        setTextColor(Color.rgb(255, 152, 0))
        setPadding(0, 0, 0, 12)
    }
    panel.addView(section)
    val row = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = android.view.Gravity.CENTER_VERTICAL
    }
    fun addTile(label: String, detail: String, action: () -> Unit) {
        val tile = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = android.view.Gravity.CENTER
            isFocusable = true
            isFocusableInTouchMode = true
            setPadding(22, 20, 22, 20)
            background = GradientDrawable().apply {
                setColor(Color.rgb(27, 34, 47))
                cornerRadius = 18f
                setStroke(2, Color.rgb(58, 68, 84))
            }
            setOnClickListener { action() }
            setOnFocusChangeListener { v, focused ->
                v.background = GradientDrawable().apply {
                    setColor(if (focused) Color.rgb(65, 42, 20) else Color.rgb(27, 34, 47))
                    cornerRadius = 18f
                    setStroke(if (focused) 4 else 2, if (focused) Color.rgb(255, 145, 0) else Color.rgb(58, 68, 84))
                }
            }
        }
        val title = TextView(this).apply {
            text = label
            textSize = 20f
            setTextColor(Color.WHITE)
            setTypeface(null, android.graphics.Typeface.BOLD)
        }
        val hint = TextView(this).apply {
            text = detail
            textSize = 13f
            setTextColor(Color.LTGRAY)
            setPadding(0, 8, 0, 0)
        }
        tile.addView(title)
        tile.addView(hint)
        row.addView(tile, LinearLayout.LayoutParams(0, 132, 1f).apply {
            setMargins(0, 0, 16, 0)
        })
        if (homeFirstTile == null) homeFirstTile = tile
    }
    addTile("Open video", "Browse files") {
        pickVideo.launch(arrayOf("video/*", "audio/*", "application/octet-stream", "application/x-matroska"))
    }
    addTile("Resume", "Continue watching") {
        val last = prefs.getString(KEY_LAST_URI, null)?.let { Uri.parse(it) }
        if (last != null) { selectMedia(last); startPlayer() }
        else Toast.makeText(this, "No previous video", Toast.LENGTH_SHORT).show()
    }
    addTile("History", "Recently played") { showHistory() }
    panel.addView(row)
    val footer = TextView(this).apply {
        text = "MENU  ·  Playback options     •     BACK  ·  Player menu"
        textSize = 13f
        setTextColor(Color.rgb(135, 148, 166))
        setPadding(0, 30, 0, 0)
    }
    panel.addView(footer)
    panel.isFocusableInTouchMode = true
    panel.descendantFocusability = android.view.ViewGroup.FOCUS_AFTER_DESCENDANTS
    panel.post { homeFirstTile?.requestFocus() }
    return panel
}
private fun showHome() {
    if (!::homePanel.isInitialized) return
    homePanel.visibility = View.VISIBLE
    playerView.visibility = View.GONE
    if (::menuButtonRef.isInitialized) menuButtonRef.visibility = View.GONE
    homePanel.descendantFocusability = android.view.ViewGroup.FOCUS_AFTER_DESCENDANTS
    homePanel.post { homeFirstTile?.requestFocus() }
}
'''
if "private fun buildHomePanel()" not in s:
    s = s.replace("    private fun showMenu() {", home_methods + "    private fun showMenu() {", 1)
s = s.replace("        playerView.player = exo\n        player = exo",
              "        playerView.player = exo\n        playerView.visibility = View.VISIBLE\n        homePanel.visibility = View.GONE\n        if (::menuButtonRef.isInitialized) menuButtonRef.visibility = View.GONE\n        player = exo", 1)
if 'add("Home")' not in s:
    s = s.replace('        add("Open video file") {', '        add("Home") { showHome() }\n        add("Open video file") {', 1)
s, home_launch_matches = re.subn(
    r'\}\s*else\s*\{\s*pickVideo\.launch\(arrayOf\([^\n]*\)\)\s*\}',
    '} else { showHome() }',
    s, count=1)
if home_launch_matches != 1:
    raise SystemExit("Could not replace first-launch picker with home screen")
p.write_text(s)
required = ['private fun buildHomePanel()', 'addTile("Open video"', 'addTile("Resume"', 'addTile("History"', 'homePanel.visibility = View.GONE']
missing_ui = [item for item in required if item not in s]
if missing_ui:
    raise SystemExit("Missing TV UI elements: " + ", ".join(missing_ui))
required = ['add("Resume last video")', 'add("Restart current video")',
            'add("History")', 'private fun showHistory()', 'subtitleUri2',
            'override fun onPositionDiscontinuity(']
missing = [item for item in required if item not in s]
if "pickSubtitle2" not in s:
    missing.append("second subtitle picker")
if missing:
    raise SystemExit("Missing features: " + ", ".join(missing))
print("Menu, resume, and independent subtitle picker hooks verified.")
