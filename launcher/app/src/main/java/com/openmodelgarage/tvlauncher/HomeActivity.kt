package com.openmodelgarage.tvlauncher

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ActivityInfo
import android.graphics.drawable.Drawable
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.text.TextUtils
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.animation.DecelerateInterpolator
import android.widget.FrameLayout
import android.widget.GridLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextClock
import android.widget.TextView
import android.widget.Toast
import java.util.concurrent.Executors

/**
 * One screen: a clock and a grid of app banners. No rows of recommendations, no network,
 * no background service. Framework views only, so a cold start stays cheap on an old TV.
 */
class HomeActivity : Activity() {

    private class App(val label: String, val pkg: String, val launch: Intent?, val info: ActivityInfo?,
                      val leanback: Boolean, val art: Int = 0)

    /** Home screen apps (director, 2026-11-18), matched by package or by a word in the app's name.
     *  FanCode gets custom art and the label "F1 Car" (its TV app is "Watch Formula 1 on FanCode"). */
    private class Fav(val pkgs: List<String>, val hint: String?, val label: String?, val art: Int)
    private val favs = listOf(
        Fav(listOf("com.google.android.youtube.tv"), null, null, 0),
        Fav(listOf("com.netflix.ninja"), null, null, 0),
        Fav(listOf("com.amazon.amazonvideo.livingroom"), "prime video", null, 0),
        Fav(listOf("in.startv.hotstar"), "hotstar", null, 0),
        Fav(listOf("com.dream11sportsguru"), "fancode", "F1 Car", R.drawable.tile_f1),
        Fav(listOf("com.android.tv.settings", "com.android.settings", "settings"), null, null, 0),
    )
    private var allApps: List<App> = emptyList()
    private var showAll = false

    private val io = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())
    private lateinit var scroll: ScrollView
    private lateinit var grid: GridLayout
    private var firstTile: View? = null
    private var generation = 0

    private val packageReceiver = object : BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) = loadApps()
    }

    // Space Grotesk (SIL OFL 1.1), static Light/Medium cut from the variable font; assets work on every API level
    private val fontLight by lazy { android.graphics.Typeface.createFromAsset(assets, "fonts/space_grotesk_light.ttf") }
    private val fontMedium by lazy { android.graphics.Typeface.createFromAsset(assets, "fonts/space_grotesk_medium.ttf") }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
    @Suppress("DEPRECATION") private fun color(id: Int) = resources.getColor(id)  // 2-arg form needs API 23

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(buildUi())
        val f = IntentFilter().apply {
            addAction(Intent.ACTION_PACKAGE_ADDED)
            addAction(Intent.ACTION_PACKAGE_REMOVED)
            addAction(Intent.ACTION_PACKAGE_CHANGED)
            addDataScheme("package")
        }
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(packageReceiver, f, RECEIVER_NOT_EXPORTED)
        else registerReceiver(packageReceiver, f)
        loadApps()
    }

    override fun onDestroy() {
        unregisterReceiver(packageReceiver)
        io.shutdownNow()
        super.onDestroy()
    }

    /** HOME pressed while already home: back to the top, first tile focused. */
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (showAll) { showAll = false; show() }
        scroll.scrollTo(0, 0)
        firstTile?.requestFocus()
    }

    @Deprecated("Back closes All apps; on the home screen it does nothing")
    override fun onBackPressed() {
        if (showAll) { showAll = false; show() }
    }

    // ------------------------------------------------------------------ layout
    private fun buildUi(): View {
        val padH = resources.getDimensionPixelSize(R.dimen.pad_h)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(color(R.color.bg))
            setPadding(0, resources.getDimensionPixelSize(R.dimen.pad_top), 0, 0)
            clipChildren = false; clipToPadding = false
        }
        // side padding lives on the header and the grid (not the root), so a focused edge tile's 1.1x zoom is not clipped
        val header = LinearLayout(this).apply { gravity = Gravity.BOTTOM; setPadding(padH, 0, padH, 0) }
        header.addView(TextClock(this).apply {
            format12Hour = "h:mm"; format24Hour = "H:mm"
            setTextColor(color(R.color.text_primary))
            textSize = resources.getDimension(R.dimen.clock_size) / resources.displayMetrics.scaledDensity
            typeface = fontLight
        })
        header.addView(View(this), LinearLayout.LayoutParams(0, 1, 1f))
        header.addView(TextClock(this).apply {
            format12Hour = "EEE d MMM"; format24Hour = "EEE d MMM"
            setTextColor(color(R.color.accent)); textSize = 18f; typeface = fontMedium
        })
        root.addView(header)

        grid = GridLayout(this).apply {
            clipChildren = false; clipToPadding = false
            setPadding(padH, dp(28), padH, dp(48))   // room for the focus lift at the top and bottom rows
        }
        scroll = ScrollView(this).apply {
            isVerticalScrollBarEnabled = false; clipChildren = false; clipToPadding = false
            isFocusable = false
            addView(grid)
        }
        root.addView(scroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        return root
    }

    // ------------------------------------------------------------------ apps
    private fun loadApps() {
        val gen = ++generation
        io.execute {
            val pm = packageManager
            val seen = HashSet<String>()
            val apps = ArrayList<App>()
            fun scan(category: String, leanback: Boolean) {
                val q = Intent(Intent.ACTION_MAIN).addCategory(category)
                for (ri in pm.queryIntentActivities(q, 0)) {
                    val ai = ri.activityInfo
                    if (ai.packageName == packageName || !seen.add(ai.packageName)) continue
                    val launch = Intent(Intent.ACTION_MAIN).addCategory(category)
                        .setComponent(ComponentName(ai.packageName, ai.name))
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED)
                    apps.add(App(ri.loadLabel(pm).toString(), ai.packageName, launch, ai, leanback))
                }
            }
            scan(Intent.CATEGORY_LEANBACK_LAUNCHER, true)
            scan(Intent.CATEGORY_LAUNCHER, false)
            apps.sortBy { it.label.lowercase() }
            if (apps.none { it.pkg == "com.android.tv.settings" || it.pkg == "com.android.settings" }) {
                apps.add(App(getString(R.string.settings), "settings",
                    Intent(Settings.ACTION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), null, false))
            }
            main.post { if (gen == generation) { allApps = apps; show() } }
        }
    }

    private fun homeApps(): List<App> {
        val out = ArrayList<App>()
        for (f in favs) {
            val a = allApps.firstOrNull { it.pkg in f.pkgs } ?: f.hint?.let { h ->
                allApps.firstOrNull { it.label.lowercase().contains(h) } } ?: continue  // not installed: no tile
            out.add(if (f.art == 0 && f.label == null) a
                    else App(f.label ?: a.label, a.pkg, a.launch, a.info, true, f.art))
        }
        out.add(App(getString(R.string.all_apps), "__all__", null, null, false))
        return out
    }

    private fun show() {
        val gen = generation
        if (showAll) render(allApps, gen, 5) else render(homeApps(), gen, 3)
    }

    private fun render(apps: List<App>, gen: Int, cols: Int) {
        val gap = resources.getDimensionPixelSize(R.dimen.tile_gap)
        val avail = resources.displayMetrics.widthPixels - 2 * resources.getDimensionPixelSize(R.dimen.pad_h)
        val tileW = (avail - gap * (cols - 1)) / cols
        val tileH = tileW * 9 / 16
        val hadFocus = grid.findFocus() != null || firstTile == null
        grid.removeAllViews()
        grid.columnCount = cols
        firstTile = null
        val icons = ArrayList<Pair<App, FrameLayout>>()
        apps.forEachIndexed { i, app ->
            val (cell, tile) = makeCell(app, tileW, tileH)
            grid.addView(cell, GridLayout.LayoutParams().apply {
                width = tileW
                setMargins(0, 0, if (i % cols == cols - 1) 0 else gap, gap / 2)
            })
            if (i == 0) firstTile = tile
            icons.add(app to tile)
        }
        if (hadFocus) firstTile?.requestFocus()
        // banners/icons are decoded off the UI thread, then dropped into their tiles
        io.execute {
            for ((app, tile) in icons) {
                if (gen != generation) return@execute
                val d = loadArt(app)
                main.post { if (gen == generation && d != null) setArt(tile, app, d) }
            }
        }
    }

    private fun loadArt(app: App): Drawable? = try {
        val pm = packageManager
        val ai = app.info
        when {
            app.art != 0 -> resources.getDrawable(app.art, theme)
            app.pkg == "__all__" -> null                       // text-only tile
            ai == null -> resources.getDrawable(android.R.drawable.ic_menu_preferences, theme)
            app.leanback -> ai.loadBanner(pm) ?: ai.applicationInfo.loadBanner(pm) ?: ai.loadIcon(pm)
            else -> ai.loadIcon(pm)
        }
    } catch (e: Exception) { null }

    private fun makeCell(app: App, w: Int, h: Int): Pair<View, FrameLayout> {
        val radius = resources.getDimension(R.dimen.tile_radius)
        val cell = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; clipChildren = false; clipToPadding = false
        }
        val tile = FrameLayout(this).apply {
            background = GradientDrawable().apply { cornerRadius = radius; setColor(color(R.color.tile)) }
            clipToOutline = true
            isFocusable = true; isClickable = true
            contentDescription = app.label
        }
        // placeholder text until the banner arrives (and for apps without one)
        tile.addView(TextView(this).apply {
            text = app.label; gravity = Gravity.CENTER; setTextColor(color(R.color.text_secondary))
            textSize = 15f; typeface = fontMedium; maxLines = 2; ellipsize = TextUtils.TruncateAt.END; setPadding(dp(8), 0, dp(8), 0)
        }, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        val label = TextView(this).apply {
            text = app.label; gravity = Gravity.CENTER; setTextColor(color(R.color.accent))
            textSize = 16f; typeface = fontMedium; maxLines = 1; ellipsize = TextUtils.TruncateAt.END; alpha = 0f
            setPadding(0, dp(14), 0, 0)
        }
        cell.addView(tile, LinearLayout.LayoutParams(w, h))
        cell.addView(label, LinearLayout.LayoutParams(w, ViewGroup.LayoutParams.WRAP_CONTENT))

        val ring = GradientDrawable().apply {
            cornerRadius = radius; setStroke(dp(3), color(R.color.focus_ring)); setColor(0)
        }
        val ease = DecelerateInterpolator()
        tile.setOnFocusChangeListener { v, focused ->
            v.animate().scaleX(if (focused) 1.1f else 1f).scaleY(if (focused) 1.1f else 1f)
                .translationZ(if (focused) dp(16).toFloat() else 0f)
                .setDuration(150).setInterpolator(ease).start()
            (v as FrameLayout).foreground = if (focused) ring else null
            label.animate().alpha(if (focused) 1f else 0f).setDuration(150).start()
        }
        tile.setOnClickListener {
            if (app.launch == null) { showAll = true; show(); return@setOnClickListener }  // "All apps"
            try { startActivity(app.launch) } catch (e: Exception) {
                Toast.makeText(this, app.label, Toast.LENGTH_SHORT).show()
            }
        }
        return cell to tile
    }

    private fun setArt(tile: FrameLayout, app: App, d: Drawable) {
        val iv = ImageView(this)
        if (app.leanback && d.intrinsicWidth > d.intrinsicHeight) {
            iv.scaleType = ImageView.ScaleType.CENTER_CROP            // a real 16:9 banner fills the tile
            tile.removeAllViews()
            tile.addView(iv, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        } else {
            iv.scaleType = ImageView.ScaleType.FIT_CENTER             // square icon centred on the tile
            tile.removeAllViews()
            val s = tile.layoutParams.height / 2
            tile.addView(iv, FrameLayout.LayoutParams(s, s, Gravity.CENTER))
        }
        iv.setImageDrawable(d)
    }
}
