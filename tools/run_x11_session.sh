#!/usr/bin/env bash
# Disposable GNOME-like X11/Adwaita desktop, not an application palette override.
set -euo pipefail
if [[ "${1:-}" == --inside ]]; then
    shift
    openbox > artifacts/build/openbox.log 2>&1 &
    dbus-update-activation-environment DISPLAY XAUTHORITY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE GDK_BACKEND XDG_CONFIG_HOME
    # Modern apps consume the Settings portal; GTK3 (including Qt's gtk3
    # platform-theme plugin) consumes the actual desktop theme through
    # XSettings. A window manager plus a portal alone is an incomplete session.
    # Start only the ordinary settings daemon, not the full GNOME desktop.
    /usr/libexec/gsd-xsettings > artifacts/build/gsd-xsettings.log 2>&1 &
    xsettings_pid=$!
    gdbus wait --session --timeout 10 org.gnome.SettingsDaemon.XSettings
    kill -0 "$xsettings_pid"
    gtk-query-settings gtk-theme-name > artifacts/build/gtk3-initial-settings.txt
    glxinfo -B > artifacts/build/glxinfo.txt
    exec "$@"
fi
desktop_config="$(mktemp -d)"
export XDG_CONFIG_HOME="$desktop_config"
mkdir -p "$XDG_CONFIG_HOME/xdg-desktop-portal"
cp tools/desktop-portals.conf "$XDG_CONFIG_HOME/xdg-desktop-portal/portals.conf"
export LIBGL_ALWAYS_SOFTWARE=1 GDK_BACKEND=x11 QT_QPA_PLATFORM=xcb
export XDG_SESSION_TYPE=x11 XDG_CURRENT_DESKTOP=GNOME
exec dbus-run-session -- xvfb-run -a -s '-screen 0 1600x1000x24' bash "$0" --inside "$@"
