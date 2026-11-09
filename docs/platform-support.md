# Desktop platform and integration support

This is a **framework capability matrix**, separate from the resource measurements.
It describes APIs and integration routes documented for egui/eframe 0.37, Slint
1.18, Qt 6, GTK 4 and Tauri 2. The small demos implement one window, fixture
navigation, text filtering and Refresh. They do not implement or qualify every
feature below. No screen-reader, IME, clipboard, drag-and-drop, tray or mixed-DPI
acceptance suite was run for this table.

**B** = framework API/integration, sometimes enabled by a Cargo feature;
**A** = additional crate, plugin or application integration;
**I** = inherited from the system WebView;
**L** = a documented platform/backend limitation;
**U** = the cited evidence does not establish that platform's complete behavior.
U does not mean unsupported. Linux columns distinguish display sessions; session
buses, input methods, shell extensions and tray hosts are additional dependencies.
The menu rows distinguish framework-rendered, in-window menus from native OS or
global menu integration; a built-in menu API does not imply OS-native rendering.

| Framework | Windows window/runtime | macOS window/runtime | Linux X11 | Linux Wayland |
| --- | --- | --- | --- | --- |
| egui / eframe | winit; this demo uses WGPU/DX12 | winit; this demo uses OpenGL | winit/X11 + OpenGL | winit/Wayland + OpenGL; Wayland feature required |
| Slint | Selected Slint backend; demo uses winit/software | Same | winit/X11/software in demo | winit/Wayland/software in demo |
| Qt Widgets | Windows platform plugin | Cocoa platform plugin | xcb platform plugin | Wayland platform plugin must be installed |
| GTK4 | Win32 backend | macOS backend | GDK X11 backend | GDK Wayland backend |
| Tauri | WebView2 | System WKWebView | System WebKitGTK, GTK display backend | System WebKitGTK, GTK display backend |

The examples explicitly select a subset of features. In particular, a framework's
default optional features do not imply that they are all enabled in these demos.
See [eframe's feature list](https://docs.rs/crate/eframe/0.37.0/features),
[Slint's feature list](https://docs.rs/crate/slint/1.18.1/features),
[Qt platform support](https://doc.qt.io/qt-6.8/supported-platforms.html),
[GTK backends](https://docs.gtk.org/gtk4/running.html#gdk-backend) and
[Tauri WebView versions](https://v2.tauri.app/reference/webview-versions/).

## egui / eframe 0.37

| Feature | Windows | macOS | Linux X11 | Linux Wayland |
| --- | --- | --- | --- | --- |
| Screen readers | B: `accesskit`, Windows UIA | B: `accesskit`, macOS accessibility | U: Unix AT-SPI adapter exists; end-to-end reader behavior unconfirmed | U: same AT-SPI qualification |
| IME | B: winit/egui composition | B: winit/egui; IME affects dead-key handling | B: winit/egui; compose/dead-key interaction | B: IME API; U for complete compositor/input-method coverage |
| Clipboard | B: clipboard feature/integration | B: same | B: same | B: clipboard and Wayland integration |
| External drag and drop | B: file-drop input when enabled; U for generic MIME payloads | B: native file-event integration; U for generic payloads | B: native file-event integration; U for generic payloads | U: native external-drop coverage; in-app egui dragging is separate |
| Menus and OS integration | B: painted egui menus; A: OS-native integration | B: painted menus; A: OS menu-bar integration | B: painted menus; A: desktop/global integration | B: painted menus; A: desktop/global integration |
| Tray | A: separate integration | A: separate integration | A: separate integration and tray host | A: separate integration and compatible host |
| Multiple windows | B: native viewports | B: native viewports | B: native viewports | B: native viewports; compositor governs placement/activation |
| HiDPI | B: winit monitor scale | B: winit display scale | B: Xft/override/fallback scale handling | B: compositor scale, fractional protocol where available |

AccessKit is an optional eframe feature enabled by eframe's defaults; this example
enables it explicitly. AccessKit documents Windows, macOS and Unix adapters, but
that is not evidence that a particular Linux screen reader works with this demo.
Sources: [eframe APIs/features](https://docs.rs/eframe/0.37.0/eframe/),
[AccessKit adapters](https://github.com/AccessKit/accesskit),
[winit IME and scale-factor platform notes](https://docs.rs/winit/0.30.13/winit/window/struct.Window.html).

File-drop input exists in [egui's raw input](https://docs.rs/egui/0.37.0/src/egui/data/input/raw_input.rs.html)
and is forwarded from native window events by
[egui-winit](https://docs.rs/egui-winit/0.37.0/src/egui_winit/lib.rs.html).
That does not establish arbitrary cross-application MIME drag-and-drop or every
Wayland backend combination. Native menus and tray integration are separate from
egui's own painted widgets.

## Slint 1.18

| Feature | Windows | macOS | Linux X11 | Linux Wayland |
| --- | --- | --- | --- | --- |
| Screen readers | B: `accessibility` feature; OS adapter | B: same | B: feature/backend integration; U for reader coverage | B: feature/backend integration; U for reader coverage |
| IME | B: text-input/backend API; U for full IME coverage | B/U: same | B/U: same | B/U: same |
| Clipboard | B: TextInput/backend cut, copy, paste | B: same | B: same | B: same; compositor/backend-dependent |
| External drag and drop | L: native external DnD documented for Qt backend; demo uses winit | L: same | L: same | L: same |
| Menus and OS integration | B: MenuBar; native versus painted depends on backend | B: same | B: same | B: same |
| Tray | B: `system-tray` feature | B: `system-tray` feature | B/L: StatusNotifier-compatible host required | B/L: compatible StatusNotifier host required |
| Multiple windows | B: Window instances | B: Window instances | B: Window instances | B: Window instances; compositor policies apply |
| HiDPI | B: window/backend scaling; U for exact backend semantics | B/U: same | B/U: same | B/U: same |

Slint's built-in `DragArea`/`DropArea` supports in-window payloads. The 1.18
changelog separately documents native application-to-application DnD for its Qt
backend; that capability must not be attributed to the measured winit/software
configuration. Accessibility and system tray are Slint feature flags; the latter
is not enabled or implemented by this demo. Sources:
[1.18.1 features](https://docs.rs/crate/slint/1.18.1/features),
[1.18.1 changes](https://github.com/slint-ui/slint/blob/v1.18.1/CHANGELOG.md),
[Qt backend platforms](https://docs.slint.dev/latest/docs/slint/guide/backends-and-renderers/backend_qt/),
[Window and MenuBar](https://docs.slint.dev/latest/docs/slint/reference/window/window/),
[SystemTrayIcon platform notes](https://docs.slint.dev/latest/docs/slint/reference/window/systemtrayicon/),
[TextInput clipboard operations](https://docs.slint.dev/latest/docs/slint/reference/keyboard-input/textinput/).

## Qt Widgets 6

| Feature | Windows | macOS | Linux X11 | Linux Wayland |
| --- | --- | --- | --- | --- |
| Screen readers | B: MSAA integration | B: macOS Accessibility | B: AT-SPI via the accessibility bus | U: retrieved QAccessible platform statement explicitly names Unix/X11 |
| IME | B: QInputMethod and platform input context | B: same | B: same; input-method plugin/session required | B: same; compositor/input-method integration required |
| Clipboard | B: QClipboard | B: QClipboard | B: QClipboard | B: QClipboard |
| External drag and drop | B: MIME-based Qt DnD | B: same | B: same | B: same; compositor interoperability applies |
| Menus and OS integration | B: in-window Qt menus | B: native global menu bar | B/L: global integration on supporting D-Bus-menu desktops, otherwise in-window | B/L: same desktop requirement |
| Tray | B: QSystemTrayIcon | B: QSystemTrayIcon | B/L: XEmbed or StatusNotifier host | B/L: StatusNotifier-compatible host |
| Multiple windows | B: top-level QWidget instances | B: same | B: same | B: same; compositor policies apply |
| HiDPI | B: per-monitor support | B: display scaling | B: DPI/backend settings | B: compositor/backend scaling; version-dependent details |

These are Qt 6 API capabilities. The published native comparison used Linux Qt
6.4.2, Windows Qt 6.8.3 and Homebrew qtbase 6.12.0_2 on macOS;
backend/version-specific behavior must be checked against the deployed version
([recorded versions](full-native-results.md#versions-and-environment)). In particular, Qt 6.8's HiDPI guide describes
integer `wl_output::scale` on Wayland; this table does not transfer that exact
limitation to every Qt release. Custom widgets need appropriate accessibility
interfaces. Tray availability can be queried at runtime. Sources:
[QAccessible](https://doc.qt.io/qt-6.8/qaccessible.html),
[QInputMethod](https://doc.qt.io/qt-6/qinputmethod.html),
[QClipboard](https://doc.qt.io/qt-6/qclipboard.html),
[drag and drop](https://doc.qt.io/qt-6/dnd.html),
[QMenuBar](https://doc.qt.io/qt-6.8/qmenubar.html),
[QSystemTrayIcon](https://doc.qt.io/qt-6.8/qsystemtrayicon.html),
[Qt 6.8 HiDPI details](https://doc.qt.io/qt-6.8/highdpi.html).

## GTK 4.14 / 4.18

| Feature | Windows | macOS | Linux X11 | Linux Wayland |
| --- | --- | --- | --- | --- |
| Screen readers | U: native platform bridge not established by the cited 4.14 evidence | U: same | B: accessible widgets and AT-SPI | B: accessible widgets and AT-SPI; session bus required |
| IME | B: IMContext API; U for native method coverage | B/U: same | B: IMContext/IMMulticontext and installed input modules | B: same, with compositor/input-method integration |
| Clipboard | B: GdkClipboard | B: GdkClipboard | B: GdkClipboard, including selection concepts | B: GdkClipboard; compositor/provider rules apply |
| External drag and drop | B: GtkDragSource/GtkDropTarget | B: same | B: same | B: same; backend interoperability applies |
| Menus and OS integration | B: in-window GTK menus | B/L: application menu integration supported by the platform | B/L: in-window menus or supporting shell integration | B/L: same shell-dependent integration |
| Tray | A: external/native integration | A: external/native integration | A: indicator/tray integration and host | A: indicator integration and compatible host |
| Multiple windows | B: GtkWindow/GtkApplication | B: same | B: same | B: same; compositor controls placement/activation |
| HiDPI | B: logical units; U for exact backend behavior | B/U: same | B: scale APIs; backend-specific | B: scale APIs; compositor-specific |

The GTK 4.14 accessibility description establishes an AT-SPI/Linux implementation;
it does not establish Windows/macOS screen-reader parity. GTK 4.14 introduced a
fractional monitor-scale query, but that API alone is not a promise of equal
fractional rendering on all backends. GTK3's deprecated `GtkStatusIcon` must not
be treated as a GTK4 tray API. Sources:
[GTK 4.14 accessibility](https://blog.gtk.org/2024/03/08/accessibility-improvements-in-gtk-4-14/),
[IMContext](https://docs.gtk.org/gtk4/class.IMContext.html),
[GTK4 clipboard migration](https://docs.gtk.org/gtk4/migrating-3to4.html),
[drag and drop](https://docs.gtk.org/gtk4/drag-and-drop.html),
[ApplicationWindow menus](https://docs.gtk.org/gtk4/class.ApplicationWindow.html),
[application/window lifecycle](https://docs.gtk.org/gtk4/class.Application.html),
[monitor scale, since 4.14](https://docs.gtk.org/gdk4/method.Monitor.get_scale.html),
[GTK3 StatusIcon](https://docs.gtk.org/gtk3/class.StatusIcon.html).

## Tauri 2

| Feature | Windows | macOS | Linux X11 | Linux Wayland |
| --- | --- | --- | --- | --- |
| Screen readers | I: WebView2 DOM accessibility; U for reader outcomes | I: WKWebView; U for reader outcomes | I: WebKitGTK; U for reader outcomes | I: WebKitGTK; U for reader outcomes |
| IME | I: WebView2 input engine | I: system WKWebView input engine | I: WebKitGTK/input-method stack | I: WebKitGTK/compositor/input-method stack |
| Clipboard | I: HTML editing copy/paste; A: programmatic clipboard plugin | I/A: same | I/A: same | I/A: same; session restrictions apply |
| External drag and drop | B: file-drop paths; L: native handler affects HTML5 DnD | B: file-drop paths; other payloads follow WebView | B: same | B: same; compositor/backend-dependent |
| Menus and OS integration | B: window/native context menus | B: application/native context menus | B: window/native context menus | B: same via GTK integration |
| Tray | B: desktop tray API | B: desktop tray API | B/L: host-dependent; Linux pointer-event limitations | B/L: compatible host required; same event limitations |
| Multiple windows | B: WebviewWindow instances | B: same | B: same | B: same; compositor policies apply |
| HiDPI | B: scaleFactor/logical size; I: WebView pixel ratio | B/I: same | B/I: same | B/I: same; compositor/backend-dependent |

The WebView engine is part of the runtime comparison: WebView2 on Windows,
system WKWebView on macOS, and distribution WebKitGTK on Linux. Tauri's engine
selection does not provide a separate guarantee for every screen reader or IME.
Copy and paste in editable HTML controls comes from the WebView engine.
Programmatic clipboard access through Tauri uses the additional clipboard-manager
plugin and requires explicit permissions. Native file drop reports
paths; Windows HTML5 frontend drag-and-drop requires disabling Tauri's default
`dragDropEnabled` handler. Linux tray pointer events are not emitted as on
Windows/macOS, although the context menu can still work. Multiple top-level
windows are distinct from the separately gated child-WebView feature. Sources:
[WebView versions](https://v2.tauri.app/reference/webview-versions/),
[clipboard plugin](https://v2.tauri.app/plugin/clipboard/),
[native menus](https://v2.tauri.app/learn/window-menu/),
[tray behavior](https://v2.tauri.app/learn/system-tray/),
[tray API limitations](https://v2.tauri.app/reference/javascript/api/namespacetray/),
[file-drop events](https://v2.tauri.app/reference/javascript/api/namespacewebview/#ondragdropevent),
[window configuration](https://v2.tauri.app/reference/config/#windowconfig),
[window and scaling APIs](https://v2.tauri.app/reference/javascript/api/namespacewindow/).
