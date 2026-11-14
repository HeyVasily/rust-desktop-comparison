# Qt Widgets comparison

A standalone C++17 control using Qt 6 Widgets. No Qt Quick, QML, WebEngine or Rust
bindings are involved. CMake accepts Qt 6.4 or newer; record the installed Qt version
alongside any measurement instead of treating the minimum as the measured version.

The initial 960×640 logical-pixel window shows All projects, project-001 and
snapshot 0, with initial keyboard focus on Refresh. It includes ten yard buttons, 100 selectable project rows, details,
an editable case-sensitive name filter, scrolling and an in-memory Refresh counter.
There is no backend, animation, or settings polling. Ctrl/Cmd+F focuses the standard
`QLineEdit`; copy/paste uses Qt's native clipboard integration.

From the repository root, with CMake, a C++ compiler and Qt 6 Widgets development
packages installed:

```sh
cmake -S examples/qt -B target/qt -DCMAKE_BUILD_TYPE=Release
cmake --build target/qt --config Release
```

Run `target/qt/veranda-qt-comparison`; Visual Studio generators normally place the
Windows executable at `target/qt/Release/veranda-qt-comparison.exe`. The window
title is `Veranda Qt Widgets comparison`. The target is a plain executable on
macOS, not an app bundle.

On Debian, install `build-essential cmake qt6-base-dev`. On Windows, use the
matching Qt MSVC kit and Visual Studio C++ tools. On macOS, use the macOS Qt kit
and Xcode command-line tools. Set `CMAKE_PREFIX_PATH` to the Qt kit prefix if CMake
cannot discover it. Qt's DLLs/frameworks and platform plugins must be reachable at
runtime; on Windows run `windeployqt` from the same kit on the built executable
before moving it outside the build environment.

## Normal desktop integration

The application does not set a stylesheet, force light or dark mode, or install a
hand-written palette. Qt obtains the platform palette, fonts, clipboard, and
settings through its platform integration. Its standard widgets repaint when the
platform palette changes. `system_theme` log lines report the actual effective
palette at startup, on `colorSchemeChanged` and on `ApplicationPaletteChange`; a requested scheme alone
is not proof that the pixels changed.

For a system-following Linux measurement, use Qt **6.8.3 or newer** and install the
matching desktop platform-theme plugin as well as the X11/Wayland platform plugin.
The Qt 6.4 minimum is only source/build compatibility, not a claim that an old or
incomplete Qt installation provides the same desktop behavior. Record the exact
Qt version and loaded plugins with the measurement.

- **GNOME-family desktop:** ship/install Qt's `gtk3` platform-theme plugin
  (`platformthemes/libqgtk3.so`) and its GTK3/QtDBus runtime dependencies, plus the
  session's Settings portal/backend and, on X11, a functioning XSettings manager.
  Qt normally selects this plugin from the actual `XDG_CURRENT_DESKTOP`. In Qt
  6.8.3 it subscribes to the portal's `org.freedesktop.appearance` preference and
  GTK theme changes without application polling. Its palette brushes still come
  from the selected **GTK3 theme**: a dark portal value alone does not turn a
  light GTK3 theme dark. This legitimately loads GTK3 in the Qt process; include
  it in the memory measurement, rather than measuring an incompletely integrated
  generic theme.
- **KDE and other Linux desktops:** retain the desktop's matching Qt platform-theme
  plugin and settings. An explicitly configured `QT_QPA_PLATFORMTHEME` is a user or
  deployment choice, not something this application overwrites. A bare window
  manager with no theme integration is not equivalent to a full desktop session.
- **Windows:** use the native Windows platform plugin with Qt's built-in **Fusion**
  widget style. The legacy Windows Vista style selected by default on the
  Windows Server 2022 runner deliberately overwrites the dark system palette
  with light colors. Fusion retains the platform-supplied palette and live
  updates; the application does not define colors or force dark mode. This is
  an explicit deployment/style choice, not a claim that Fusion draws native
  Win32 controls. The workflow pins Qt 6.8.3. See Qt's
  [explanation of the style limitation](https://www.qt.io/blog/dark-mode-on-windows-11-with-qt-6.5)
  and the pinned [Vista palette implementation](https://github.com/qt/qtbase/blob/v6.8.3/src/plugins/styles/modernwindows/qwindowsvistastyle.cpp).
- **macOS:** retain the native Qt platform plugin and style; each run records its
  Qt kit version. Validate startup and live transitions on each OS independently.
  No Linux dependencies or manual dark palette are introduced on either platform.

On Debian/Ubuntu the distribution's GTK integration is typically packaged as
`qt6-gtk-platformtheme`; it must match the distribution's Qt version. Do not mix
that plugin with a different downloaded Qt kit. A separately installed Qt kit
must include its own matching plugin. `QT_DEBUG_PLUGINS=1` is useful for diagnosing
which plugin was actually loaded, but a plugin-loading log does not replace a
live theme or external clipboard test.

The Linux runner uses a named **GNOME-like X11/Adwaita profile**: Openbox,
`gsd-xsettings`, the GTK Settings portal backend, and the installed
Adwaita/Adwaita-dark themes. Its system appearance switch updates both
`org.gnome.desktop.interface color-scheme` and `gtk-theme`, equally for every
candidate. The probe independently reads both the portal and the GTK3 settings
seen by `gtk-query-settings`; neither `GTK_THEME` nor a Qt palette is forced.
This models a coherent desktop appearance setting, not a claim that every
GNOME version or distribution synchronizes the two preferences. For example,
Ubuntu 24.04's control-center patch synchronizes its Yaru theme with the selected
color scheme, whereas stock GNOME's appearance preference need not change the
legacy GTK3 theme. Initial smoke failures from a portal-only, otherwise
incomplete session remain diagnostics of that earlier configuration.

Primary implementation references for the pinned Qt version:

- [Qt 6.8 palette behavior and platform styles](https://doc.qt.io/qt-6.8/qapplication.html#setPalette)
- [QStyleHints color-scheme contract](https://doc.qt.io/qt-6.8/qstylehints.html#colorScheme-prop)
- [Qt 6.8.3 GTK portal startup and signal integration](https://github.com/qt/qtbase/blob/v6.8.3/src/plugins/platformthemes/gtk3/qgtk3portalinterface.cpp)
- [Qt 6.8.3 system palette refresh](https://github.com/qt/qtbase/blob/v6.8.3/src/plugins/platformthemes/gtk3/qgtk3storage.cpp)
- [GTK3 system settings and XSettings](https://docs.gtk.org/gtk3/class.Settings.html)
- [GNOME 46 gtk-theme to XSettings translation](https://github.com/GNOME/gnome-settings-daemon/blob/46.0/plugins/xsettings/gsd-xsettings-manager.c)
- [Ubuntu 24.04 control-center source packaging](https://packages.ubuntu.com/noble/gnome-control-center): version `1:46.0.1-1ubuntu7`, patch `ubuntu/background-Allow-configuring-the-ubuntu-accent-color.patch` in its Debian source archive

[main.cpp](main.cpp) contains the complete widget tree and event connections.
This source is independent of the historical Qt frontend; earlier measurements
do not measure this program. Qt retains its own
[licensing terms](https://doc.qt.io/qt-6/licensing.html).
