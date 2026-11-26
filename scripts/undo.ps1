# Windows version of undo.sh: re-enable every app switched off with `pm disable-user`, give Home back to Google's TV
# home screen, and optionally remove OMG Home.
#   powershell -ExecutionPolicy Bypass -File scripts\undo.ps1 -Serial <tv-ip>:5555
#   powershell -ExecutionPolicy Bypass -File scripts\undo.ps1 -Serial <tv-ip>:5555 -RemoveOmgHome
param([string]$Serial = $env:ADB_SERIAL, [switch]$RemoveOmgHome, [string]$Adb = $(if ($env:ADB) { $env:ADB } else { "adb" }))

function A { if ($Serial) { & $Adb -s $Serial @args } else { & $Adb @args } }

A get-state | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Error "No TV connected: run 'adb connect <tv-ip>:5555' first."; exit 1 }

Write-Host "1/3 Re-enabling apps that were disabled with pm disable-user..."
$n = 0
$pkgs = A shell pm list packages -d | ForEach-Object { ($_ -replace '^package:', '').Trim() } | Where-Object { $_ }
foreach ($p in $pkgs) {
  if ((A shell dumpsys package $p) -match 'enabled=3') {   # 3 = COMPONENT_ENABLED_STATE_DISABLED_USER
    A shell pm enable $p
    $n++
  }
}
Write-Host "    re-enabled $n app(s)"

Write-Host "2/3 Giving the Home button back to Google's TV home screen..."
A shell pm enable com.google.android.tvlauncher | Out-Null
A shell cmd package set-home-activity com.google.android.tvlauncher/.MainActivity

if ($RemoveOmgHome) { Write-Host "3/3 Removing OMG Home..."; A uninstall com.openmodelgarage.tvlauncher }
else { Write-Host "3/3 OMG Home kept installed (add -RemoveOmgHome to remove it)" }
A shell input keyevent KEYCODE_HOME
Write-Host "Done. A restart of the TV is a good idea."
