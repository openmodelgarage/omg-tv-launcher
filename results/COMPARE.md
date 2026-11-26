# Before / after comparison

Stages: **before** (2026-11-18T00:44, home com.google.android.tvlauncher) → **debloat** (2026-11-18T01:34, home com.google.android.tvlauncher) → **after** (2026-11-18T07:16, home com.openmodelgarage.tvlauncher)

Median of the repetitions; [min–max] in brackets. 'overlap' = the first and last ranges overlap, so the difference may be noise. Lower is better for times, jank, CPU and used RAM.

| Test | Item | Metric | before | debloat | after | Change | Verdict |
|---|---|---|---|---|---|---|---|
| boot | uptime | boot_progress_start_ms (ms) | 6192 [6079–6205] | 6051 [6044–6152] | 6107 [6068–6165] | -1.4% | better (overlap) |
| boot | uptime | boot_progress_system_run_ms (ms) | 11523 [11506–11619] | 11506 [11448–11521] | 11586 [11432–12013] | +0.5% | worse (overlap) |
| boot | uptime | boot_progress_ams_ready_ms (ms) | 16797 [16613–17857] | 16761 [16739–16842] | 16884 [16680–17226] | +0.5% | worse (overlap) |
| boot | uptime | boot_progress_enable_screen_ms (ms) | 19029 [18831–19907] | 18994 [18951–19067] | 19000 [18920–19529] | -0.2% | better (overlap) |
| boot | uptime | launcher_first_frame_logged_ms (ms) | 28234 [23911–29183] | 27832 [27507–28351] | 22792 [17464–23251] | -19.3% | better |
| boot | uptime | settled_cpu_under_40pct_ms (ms) | 106500 [104680–119850] | 97940 [77100–101010] | 71100 [66740–73500] | -33.2% | better |
| input_overhead | input keyevent | roundtrip_ms (ms) | 1011 [982–1947] | 999 [969–1676] | 971 [948–1422] | -4.0% | better (overlap) |
| home | HOME intent | TotalTime (ms) | 254 [229–509] | 288 [226–419] | 82 [74–84] | -67.7% | better |
| home | HOME intent | WaitTime (ms) | 283 [258–535] | 319 [258–449] | 94 [92–97] | -66.8% | better |
| launcher_cold | (launcher) | TotalTime (ms) | 3616 [3579–3715] | 3691 [3617–3756] | 2489 [2438–2523] | -31.2% | better |
| launcher_cold | (launcher) | WaitTime (ms) | 1402 [1361–1475] | 1469 [1381–1530] | 276 [248–315] | -80.3% | better |
| launch_cold | com.android.tv.settings | TotalTime (ms) | 695 [684–928] | 726 [680–750] | 680 [665–723] | -2.2% | better (overlap) |
| launch_cold | com.android.tv.settings | WaitTime (ms) | 749 [735–1049] | 791 [724–800] | 718 [708–766] | -4.1% | better (overlap) |
| launch_warm | com.android.tv.settings | TotalTime (ms) | 184 [172–209] | 183 [161–379] | 183 [143–201] | -0.5% | better (overlap) |
| launch_warm | com.android.tv.settings | WaitTime (ms) | 195 [181–223] | 195 [177–398] | 193 [152–215] | -1.0% | better (overlap) |
| launch_cold | com.google.android.youtube.tv | TotalTime (ms) | 860 [804–1052] | 1057 [820–1080] | 802 [794–1112] | -6.7% | better (overlap) |
| launch_cold | com.google.android.youtube.tv | WaitTime (ms) | 916 [864–1123] | 1128 [878–1260] | 841 [832–1165] | -8.2% | better (overlap) |
| launch_warm | com.google.android.youtube.tv | TotalTime (ms) | 0 [0–0] | 0 [0–0] | 0 [0–0] | – | same/neutral (overlap) |
| launch_warm | com.google.android.youtube.tv | WaitTime (ms) | 106 [104–129] | 208 [178–257] | 78 [64–86] | -26.4% | better |
| launch_cold | com.amazon.amazonvideo.livingroom | TotalTime (ms) | 1231 [1132–47027] | 959 [903–47176] | 942 [878–45177] | -23.5% | better (overlap) |
| launch_cold | com.amazon.amazonvideo.livingroom | WaitTime (ms) | 1362 [1240–1815] | 1012 [945–1307] | 992 [913–1161] | -27.2% | better |
| launch_warm | com.amazon.amazonvideo.livingroom | TotalTime (ms) | 128 [108–2158] | 121 [36–2754] | 107 [92–2325] | -16.4% | better (overlap) |
| launch_warm | com.amazon.amazonvideo.livingroom | WaitTime (ms) | 142 [122–2184] | 139 [116–2781] | 122 [102–2343] | -14.1% | better (overlap) |
| launch_cold | in.startv.hotstar | TotalTime (ms) | 2353 [2223–2576] | 2433 [2110–2570] | 2254 [2097–2535] | -4.2% | better (overlap) |
| launch_cold | in.startv.hotstar | WaitTime (ms) | 2407 [2274–2670] | 2507 [2158–2654] | 2288 [2131–2601] | -4.9% | better (overlap) |
| launch_warm | in.startv.hotstar | TotalTime (ms) | 184 [166–301] | 226 [154–464] | 171 [128–195] | -7.1% | better (overlap) |
| launch_warm | in.startv.hotstar | WaitTime (ms) | 193 [181–313] | 248 [173–486] | 182 [138–208] | -5.7% | better (overlap) |
| scroll | (launcher) | path_seconds (s) | 38.6 [38.2–39.5] | 38.1 [37.6–38.7] | 36.9 [36.8–37.0] | -4.4% | better |
| scroll | (launcher) | frames (count) | 393.0 [341.0–499.0] | 365.0 [297.0–471.0] | 122.0 [120.0–122.0] | -69.0% | worse |
| scroll | (launcher) | janky (count) | 31.0 [29.0–82.0] | 18.0 [9.0–60.0] | 0.0 [0.0–1.0] | -100.0% | better |
| scroll | (launcher) | janky_pct (%) | 9.09 [7.38–20.6] | 6.06 [2.46–12.74] | 0.0 [0.0–0.82] | -100.0% | better |
| scroll | (launcher) | p50_ms (ms) | 7.0 [7.0–8.0] | 6.0 [6.0–7.0] | 5.0 [5.0–6.0] | -28.6% | better |
| scroll | (launcher) | p90_ms (ms) | 16.0 [15.0–21.0] | 15.0 [13.0–18.0] | 6.0 [6.0–7.0] | -62.5% | better |
| scroll | (launcher) | p95_ms (ms) | 19.0 [18.0–27.0] | 17.0 [14.0–23.0] | 7.0 [7.0–7.0] | -63.2% | better |
| scroll | (launcher) | p99_ms (ms) | 53.0 [30.0–125.0] | 29.0 [28.0–89.0] | 8.0 [7.0–10.0] | -84.9% | better |
| scroll | (launcher) | missed_vsync (count) | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | – | same/neutral (overlap) |
| scroll | (launcher) | slow_ui_thread (count) | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | 0.0 [0.0–0.0] | – | same/neutral (overlap) |
| idle | system | cpu_busy_pct_30s (%) | 13.4 [12.3–14.8] | 12.3 [11.9–12.7] | 7.6 [7.5–7.8] | -43.3% | better |
| idle | system | MemAvailable_mb (MB) | 291 [241–301] | 304 [294–306] | 376 [376–377] | +29.2% | better |
| idle | system | MemFree_mb (MB) | 131 [80–137] | 74 [69–77] | 98 [97–101] | -25.2% | worse (overlap) |
| idle | system | Cached_mb (MB) | 235 [230–240] | 298 [294–300] | 345 [343–346] | +46.8% | better |
| idle | system | free_ram_mb (MB) | 395 [360–403] | 356 [346–369] | 430 [429–433] | +8.9% | better |
| idle | system | used_ram_mb (MB) | 573 [568–578] | 612 [603–613] | 553 [552–554] | -3.5% | better |
| idle | system | lost_ram_mb (MB) | 143 [126–172] | 127 [122–139] | 78 [77–78] | -45.5% | better |
| idle | (launcher) | launcher_pss_mb (MB) | 98.7 [93.0–100.2] | 102.5 [102.4–106.8] | 17.7 [16.3–17.7] | -82.1% | better |
| idle | system | process_count (count) | 255 [253–256] | 249 [249–251] | 248 [248–249] | -2.7% | better |
