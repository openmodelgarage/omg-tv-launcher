#!/bin/sh
# Put an Android TV back the way it was: re-enable every app that was switched off with `pm disable-user`,
# give the Home button back to Google's TV home screen, and (optionally) remove OMG Home.
#
#   ADB_SERIAL=<tv-ip>:5555 sh scripts/undo.sh                    (or with only one device connected: sh scripts/undo.sh)
#   ADB_SERIAL=<tv-ip>:5555 sh scripts/undo.sh --remove-omg-home   (also uninstall OMG Home)
#
# It only re-enables apps in the "disabled-user" state (what `pm disable-user` sets). Apps the manufacturer shipped
# disabled are left alone. Nothing is uninstalled except OMG Home, and only with --remove-omg-home.
set -eu
ADB="${ADB:-adb}"
a() { if [ -n "${ADB_SERIAL:-}" ]; then "$ADB" -s "$ADB_SERIAL" "$@"; else "$ADB" "$@"; fi; }

a get-state >/dev/null || { echo "No TV connected: run 'adb connect <tv-ip>:5555' first." >&2; exit 1; }

echo "1/3 Re-enabling apps that were disabled with pm disable-user..."
n=0
for p in $(a shell pm list packages -d | tr -d '\r' | sed -n 's/^package://p'); do
  if a shell dumpsys package "$p" | tr -d '\r' | grep -q 'enabled=3'; then   # 3 = COMPONENT_ENABLED_STATE_DISABLED_USER
    a shell pm enable "$p"
    n=$((n + 1))
  fi
done
echo "    re-enabled $n app(s)"

echo "2/3 Giving the Home button back to Google's TV home screen..."
a shell pm enable com.google.android.tvlauncher >/dev/null || true
a shell cmd package set-home-activity com.google.android.tvlauncher/.MainActivity

if [ "${1:-}" = "--remove-omg-home" ]; then
  echo "3/3 Removing OMG Home..."
  a uninstall com.openmodelgarage.tvlauncher || true
else
  echo "3/3 OMG Home kept installed (add --remove-omg-home to remove it)"
fi
a shell input keyevent KEYCODE_HOME
echo "Done. A restart of the TV is a good idea."
