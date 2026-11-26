# OMG Home: a 122 KB home screen for an old Android TV

**Open Model Garage · Episode 2** · Video: [youtu.be/NbcGmTiTKIM](https://youtu.be/NbcGmTiTKIM)

My 5-year-old Android TV (1 GB RAM) took over 70 seconds to show its app list. I measured it over ADB, cleaned it up,
then replaced Google's home screen with my own, and measured again with the same tests on the same TV.

> ## ⚠ Disclaimer
> This is an **experiment on my own TV, not a tutorial**. Changing system apps or the home screen can break a TV or stop it from
> starting ("brick" it). Every TV and firmware is different. If you try anything here, it's **at your own risk**: I'm not
> responsible for any damage. Don't try it on a TV you can't afford to lose.

## Results

Same TV, same script over ADB, same apps installed. Each value is the **median of 5 runs**; every single run is in `results/`.

| | 1 · Stock | 2 · Clean-up only | 3 · Clean-up + OMG Home |
|---|---:|---:|---:|
| Home screen app's own memory | 99 MB | 103 MB | **18 MB** |
| Free memory for apps (MemAvailable, of 991 MB) ¹ | 291 MB | 304 MB | **376 MB** |
| CPU busy while idle ¹ | 13.4 % | 12.3 % | **7.6 %** |
| Power-on until the TV calms down (CPU < 40 %) | 106.5 s | 97.9 s | **71.1 s** |
| Power-on until the home screen's first frame | 28.2 s | 27.8 s | **22.8 s** |
| Home button to home screen | 254 ms | 288 ms | **82 ms** |
| Home screen cold start | 3.6 s | 3.7 s | **2.5 s** |
| Slowest 1 % of frames while moving around ² | 53 ms | 29 ms | **8 ms** |

**What did NOT change:** opening apps. Cold start, stock → OMG Home: YouTube 0.86 → 0.80 s, Prime Video 1.23 → 0.94 s,
JioHotstar 2.35 → 2.25 s, Settings 0.70 → 0.68 s (within run-to-run noise). A home screen can't make other apps' code faster.
Netflix still starts itself at every power-on (about 87 MB); without root it can't be stopped.

¹ Measured at idle after the same test sequence on each setup. ² OMG Home draws fewer frames on the same button path
(122 vs 393 on Google's home screen): it simply has less to animate.

**The clean-up alone barely helped.** Setup 2 disabled 21 pre-installed apps the TV never used (analytics/telemetry,
recommendation rows, unused media apps, a camera app on a TV with no camera). **I'm not publishing that list on purpose:** the right
list depends on the exact TV and firmware, and the wrong one can stop a TV from starting. The big gains came from replacing the
home screen (setup 3, which also has Google's home screen switched off).

Full table with min/max for every metric: [`results/COMPARE.md`](results/COMPARE.md). Charts: [`charts/`](charts/).

## What OMG Home is

One screen, six tiles (YouTube, Netflix, Prime Video, JioHotstar, Settings, All apps), a red focus ring for the remote.
No ads, no autoplay, no account, **zero permissions**, about 122 KB. Kotlin, no libraries. Edit the tiles in
[`HomeActivity.kt`](launcher/app/src/main/java/com/openmodelgarage/tvlauncher/HomeActivity.kt).

## Install (from source)

You need: a computer with [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) (`adb`),
**JDK 17 or newer** and the Android SDK (Android Studio installs both; if Gradle says "requires Java 17", point `JAVA_HOME`
at Android Studio's bundled `jbr` folder).

1. On the TV: Settings → Device Preferences → About → click **Build** 7 times. Then Developer options → turn on
   **USB debugging** / **Network debugging**. Note the TV's IP address (Settings → Network).
2. Connect: `adb connect <tv-ip>:5555` and accept the prompt on the TV.
3. Build: `cd launcher` then `./gradlew assembleRelease` (Windows: `gradlew.bat assembleRelease`). If Gradle can't find the SDK,
   set `ANDROID_HOME`, or create `launcher/local.properties` with `sdk.dir=<path to your Android SDK>` (on Windows use forward
   slashes, e.g. `sdk.dir=C:/Android/Sdk`: a backslash is read as an escape).
   The APK is signed with the debug key: it's for sideloading on your own TV, not for a store.
4. Install: `adb install -r app/build/outputs/apk/release/app-release.apk`
5. Make it the Home app: `adb shell cmd package set-home-activity com.openmodelgarage.tvlauncher/.HomeActivity`,
   then press **Home** on the remote.

That's enough to use OMG Home. In the video I also switched Google's home screen off for the measurements; you don't need to,
and `scripts/undo.sh` turns it back on.

## Undo (put the TV back)

```sh
ADB_SERIAL=<tv-ip>:5555 sh scripts/undo.sh                     # macOS / Linux / Git Bash
ADB_SERIAL=<tv-ip>:5555 sh scripts/undo.sh --remove-omg-home    # also uninstall OMG Home
```
```powershell
powershell -ExecutionPolicy Bypass -File scripts\undo.ps1 -Serial <tv-ip>:5555 [-RemoveOmgHome]
```
It re-enables **every** app that was switched off with `pm disable-user` (apps the manufacturer shipped disabled are left
alone), gives the Home button back to Google's TV home screen, and optionally removes OMG Home. Nothing else is touched.

## Measure your own TV

The same scripts that made the table above (Python 3.10+, `adb` on PATH or in `ADB`):

```sh
cd bench
python tv_bench.py --label before                              # home, launch, scroll and idle tests, 5 runs each
python tv_bench.py --label before --tests boot --allow-reboot  # power-on tests (restarts the TV 5 times)
# ...change something, then run the same commands with --label after
python compare.py results/before_* results/after_*             # writes COMPARE.md, compare.csv, compare.json
python charts.py                                               # SVG charts from compare.json
```
Results go to `bench/results/<label>_<time>/`. `raw/` there holds the full `dumpsys` output: it can contain your account name and
network details, so check it before sharing. (The raw dumps behind this repo's numbers are not published for that reason;
`bg_procs.py` needs them, so `results/background_apps.json` is included instead.)

## Credits

Built with **[Claude Code](https://claude.com/claude-code)**, an AI coding agent by Anthropic: it ran the ADB commands, wrote the
launcher and ran every benchmark, directed by me. Font: Space Grotesk (SIL Open Font License, see `launcher/FONT_LICENSE_SpaceGrotesk_OFL.txt`).
Code: MIT licence (see `LICENSE`). Android, Google TV, Xiaomi, Netflix, YouTube, Prime Video and JioHotstar are trademarks of their owners;
this project isn't affiliated with any of them.
