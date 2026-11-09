# Rust desktop GUI comparison

**[Open the interactive comparison →](https://heyvasily.github.io/rust-desktop-comparison/)**
&nbsp;·&nbsp; [Native features](docs/features.md)
&nbsp;·&nbsp; [Full measurements](docs/full-native-results.md)
&nbsp;·&nbsp; [Raw data](measurements/native-matrix-2026-11-09/summary.csv)
&nbsp;·&nbsp; [Methodology](docs/methodology.md)

The same small desktop interface built five times — **egui/eframe, GTK4 (gtk4-rs),
Slint, Qt Widgets and Tauri** — then measured five times on fresh GitHub-hosted
Windows, macOS and Linux runners, with real screenshots in light and dark mode,
the layout code and a sourced matrix of native OS features.

Every example shows 10 synthetic yards and 100 projects: navigation, selection,
scrolling, an editable filter and a Refresh button that advances an in-memory
snapshot. There is no backend or periodic work, so the numbers show what a toolkit
costs before your application does anything.

| Framework | Language here | UI model | Example |
| --- | --- | --- | --- |
| egui/eframe 0.37.0 | Rust | Immediate mode, own drawing (OpenGL/wgpu) | [main.rs](examples/egui/src/main.rs) |
| GTK4 via gtk4-rs 0.11.5 | Rust | Retained widget tree, GTK theme | [main.rs](examples/gtk/src/main.rs) |
| Slint 1.18.1 | Rust + `.slint` markup | Declarative, own renderer (software here) | [main.slint](examples/slint/ui/main.slint) |
| Qt Widgets | C++17 | Retained widget tree, platform styles | [main.cpp](examples/qt/main.cpp) |
| Tauri 2.12.5 | Rust + HTML/CSS/JS | System webview | [index.html](examples/tauri/frontend/index.html) |

## Idle memory on three operating systems

Memory of the whole application process family (including webview helpers) with a
960×640 window, as each OS's own monitor reports it: **Linux PSS**, **Windows
private working set** (Task Manager) and **macOS physical footprint** (Activity
Monitor). Median of five runs on separate VMs, with the range in brackets.
**Lower is better.** Compare rows within a column.

| Framework | Linux PSS, MiB | Windows private WS, MiB | macOS footprint, MiB |
| --- | ---: | ---: | ---: |
| egui / eframe | 96.4 [95.9–96.6] | 26.9 [26.3–29.4] | 28.2 [27.3–30.6] |
| GTK4 (gtk4-rs) | 211.7 [211.5–212.0] | 33.2 [33.0–33.4] | 43.7 [36.0–46.1] |
| Slint | **17.5** [17.4–17.7] | **9.0** [9.0–9.1] | **17.1** [16.9–17.2] |
| Qt Widgets | 23.0 [22.9–23.0] | 15.0 [15.0–15.2] | 24.2 [24.1–24.5] |
| Tauri | 338.2 [337.1–340.1] | 116.2 [115.9–116.4] | 40.8 [40.4–41.1] |

Idle CPU stayed below 0.11 % of one core everywhere, too small to rank. The
[full report](docs/full-native-results.md) adds summed RSS / Working Set, CPU,
outliers, executable sizes and versions.

> [!NOTE]
> **How to read these numbers.** PSS and footprint count shared libraries
> proportionally, so multi-process apps are no longer double-counted (Tauri on
> Linux: 501 MiB summed RSS → 338 MiB PSS). Linux ran under Xvfb with Mesa llvmpipe;
> GL-based toolkits (GTK 4.14, egui) carry its private allocations there, and the GTK
> renderer was not pinned. These are idle UI-only observations, not startup,
> interaction or frame-rate measurements. Earlier series:
> [2026-11-07 single run with GTK in C](docs/native-matrix-2026-11-07.md) and the
> [backend-connected Wayland measurements](docs/historical-comparison.md#why-the-current-linux-numbers-differ).

## Executable size and dark mode

| Framework | Executable, Linux / Windows / macOS | Follows system dark mode, Win / mac / Linux |
| --- | --- | --- |
| egui / eframe | 12.0 / 12.8 / 5.4 MiB | ✅ / ✅ / ❌ |
| GTK4 (gtk4-rs) | 0.4 / 2.1 / 0.4 MiB + GTK runtime | ❌ / ❌ / ❌ |
| Slint | 19.6 / 12.8 / 11.7 MiB | ✅ / ✅ / ✅ |
| Qt Widgets | 0.03 / 0.05 / 0.07 MiB + Qt runtime (49 MiB deployed on Windows) | ❌ / ✅ / ❌ |
| Tauri | 6.6 / 8.2 / 6.3 MiB + system webview | ✅ / ✅ / ✅ (app CSS) |

Dark mode was tested by switching the OS itself to dark and relaunching each example;
see the [captures](docs/full-native-results.md#system-dark-mode).

## Linux: X11 versus Wayland, and GTK's renderer

Two controlled Linux series explain most of the Linux differences above.

**[GTK renderer experiment](docs/gtk-memory-investigation.md).** One GTK 4.14
binary (the [C control](examples/gtk-c/main.c)) on one Ubuntu runner: the default
OpenGL renderer under Mesa llvmpipe used **238.36 MiB RSS / 209.67 MiB PSS**, while
`GSK_RENDERER=cairo` used **97.87 / 67.86 MiB**. On Debian, X11/Cairo still loaded
Mesa/LLVM (119.45 MiB); disabling GL/Vulkan as well gave 31.68 MiB with
byte-identical screenshots. The 212 MiB gtk4-rs PSS above uses the same default
renderer, so it is mostly the software-GL path, not GTK's widget tree.

**[Paired X11 and native Wayland](docs/linux-display-comparison.md).** One binary per
framework on one Ubuntu 24.04 runner, X11 (Xvfb/Openbox) versus native Wayland
(labwc), median application-family MiB:

| Framework | X11 RSS | Wayland RSS | X11 PSS | Wayland PSS |
| --- | ---: | ---: | ---: | ---: |
| egui / eframe | 117.25 | 119.25 | 91.81 | 111.45 |
| GTK4 (C control) | 181.18 | 185.89 | 151.29 | 172.42 |
| Slint | 22.77 | 23.25 | 17.50 | 17.61 |
| Qt Widgets | 33.69 | **84.50** | 22.92 | **72.92** |
| Tauri | 492.98 | 500.18 | 323.45 | 342.61 |

Qt on Wayland maps 46.77 MiB of resident LLVM/Gallium that its X11 process does not;
the report separates that observation from a causal claim. Slint barely changes.
These are software-rendered idle runs; compositor memory is excluded.

## Native features and OS integration

How much of the operating system each toolkit reaches without extra work.
Every cell links to its source in the [detailed matrix](docs/features.md); the
[per-session platform notes](docs/platform-support.md) split Linux into X11 and Wayland.

<!-- features:start -->
<!-- Generated by tools/render_features.py from data/features.json. -->
| Capability | egui / eframe | GTK4 | Slint | Qt Widgets | Tauri |
| --- | :---: | :---: | :---: | :---: | :---: |
| Native-looking controls | ❌ | 🟡 Win<br>🟡 mac<br>✅ Linux | 🟡 | ✅ Win<br>✅ mac<br>🟡 Linux | 🟡 |
| Follows system light/dark | ✅ Win<br>✅ mac<br>❌ Linux | ❌ | ✅ | ❌ Win<br>✅ mac<br>❌ Linux | ✅ |
| Native Wayland and X11 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Translucent window materials | 📦 Win<br>📦 mac<br>❌ Linux | ❌ | 📦 Win<br>📦 mac<br>❌ Linux | 🛠️ | ✅ Win<br>✅ mac<br>❌ Linux |
| Screen readers | ✅ | 🟡 Win<br>🟡 mac<br>✅ Linux | ✅ | ✅ | ✅ |
| Input methods (CJK, dead keys) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Right-to-left and bidi text | ❌ | ✅ | 🟡 | ✅ | ✅ |
| Native menu bar | 📦 | 🟡 Win<br>✅ mac<br>🟡 Linux | ✅ Win<br>✅ mac<br>🟡 Linux | ✅ | ✅ |
| System tray icon | 📦 | 📦 | ✅ | ✅ | ✅ |
| Native file dialogs | 📦 | ✅ | 📦 | ✅ | 🧩 |
| Desktop notifications | 📦 | ❔ Win<br>❔ mac<br>✅ Linux | 📦 | 🟡 | 🧩 |
| Drag and drop with other apps | 🟡 | ✅ | 🟡 | ✅ | 🟡 |
| Multiple windows | ✅ | ✅ | ✅ | ✅ | ✅ |
| System credential store | 📦 | 📦 | 📦 | 📦 | 📦 |
| Badge on the app icon | 🛠️ | 🛠️ | 🛠️ | ✅ Win<br>✅ mac<br>🟡 Linux | 🟡 Win<br>✅ mac<br>🟡 Linux |
| Progress on the app icon | 🛠️ | 🛠️ | 🛠️ | 🛠️ | ✅ Win<br>✅ mac<br>🟡 Linux |
| Request attention | ✅ | 🛠️ Win<br>🛠️ mac<br>🟡 Linux | 🟡 | ✅ Win<br>✅ mac<br>🟡 Linux | ✅ |
| Dock menu or jump list | 🛠️ | 🛠️ | 🛠️ | 🛠️ Win<br>✅ mac<br>🛠️ Linux | 🛠️ |
| Menu-bar or background-only app | ✅ Win<br>🟡 mac<br>❌ Linux | 🛠️ | 🟡 Win<br>🟡 mac<br>❌ Linux | 🟡 | ✅ |
| Tray clicks and menu | 📦 | 📦 | ✅ Win<br>🟡 mac<br>✅ Linux | ✅ | ✅ Win<br>✅ mac<br>🟡 Linux |
| Global keyboard shortcuts | 📦 Win<br>📦 mac<br>🟡 Linux | 📦 Win<br>❌ mac<br>🟡 Linux | 📦 Win<br>📦 mac<br>🟡 Linux | 📦 Win<br>📦 mac<br>🟡 Linux | 🧩 Win<br>🧩 mac<br>🟡 Linux |
| Start at login | 📦 | 📦 | 📦 | 🛠️ | 🧩 |
| Single instance | 📦 | ✅ Win<br>❌ mac<br>✅ Linux | 📦 | 📦 | 🧩 |
| URL schemes and file associations | 🛠️ | 🟡 Win<br>❔ mac<br>✅ Linux | 🛠️ | 🟡 Win<br>✅ mac<br>🟡 Linux | 🧩 |
| Installers and updates | 📦 | 🟡 Win<br>🟡 mac<br>✅ Linux | 📦 | 🟡 | ✅ |

✅ Built in · 🟡 Partial · 🧩 Official plugin · 📦 Third-party crate · 🛠️ Own platform code · ❌ Not available · ❔ Not verified. Checked 2026-11-09.
<!-- features:end -->

### Tray, badge, shortcut and single instance, tested

A [separate runner check](docs/shell-integration.md) built every example with an
optional `shell-checks` feature and looked for the effect from outside the app.
Tray icons appeared on all three systems for all five toolkits (GTK 4 through the
tray-icon crate); tray clicks reached every app except Tauri on Linux. Qt and Tauri
set Dock/taskbar badges; egui, GTK and Slint have no badge API. Global shortcuts
fired everywhere except inside GTK on macOS, and GTK's built-in single-instance
handling worked on Linux and Windows but not on macOS. Qt 6.4's attention request
was not visible on X11.

![Status items in the macOS menu bar, and the Windows taskbar with Qt's overlay badge, Tauri's overlay icon and the tray tooltip](screenshots/shell-checks-2026-11-09/menu-and-task-bars.png)

## What the interfaces look like

Real **960×640 Linux client captures** from the measured runs: all projects,
project-001 selected, empty filter. The [interactive page](https://heyvasily.github.io/rust-desktop-comparison/#screenshots)
and the [full gallery](docs/full-native-results.md#interfaces-captured-during-measurement)
show Windows, macOS and dark mode.

<table>
  <tr>
    <td width="50%"><b>egui / eframe</b><br><img src="screenshots/native-42538198685/ubuntu-24.04/egui.png" alt="egui / eframe on Linux"></td>
    <td width="50%"><b>GTK4 (gtk4-rs)</b><br><img src="screenshots/native-42538198685/ubuntu-24.04/gtk.png" alt="GTK4 via gtk4-rs on Linux"></td>
  </tr>
  <tr>
    <td><b>Slint</b><br><img src="screenshots/native-42538198685/ubuntu-24.04/slint.png" alt="Slint on Linux"></td>
    <td><b>Qt Widgets</b><br><img src="screenshots/native-42538198685/ubuntu-24.04/qt.png" alt="Qt Widgets on Linux"></td>
  </tr>
  <tr>
    <td><b>Tauri / WebKitGTK</b><br><img src="screenshots/native-42538198685/ubuntu-24.04/tauri.png" alt="Tauri / WebKitGTK on Linux"></td>
    <td><b>Slint, system dark mode</b><br><img src="screenshots/native-42538198685/ubuntu-24.04/slint-dark.png" alt="Slint on Linux in system dark mode"></td>
  </tr>
</table>

## What the layout code looks like

| Framework | Layout in these examples | State and events |
| --- | --- | --- |
| egui/eframe | Rust panel/widget calls inside `App::ui` | Rust fields; widget responses update state |
| GTK4 (gtk4-rs) | Rust builds persistent `GtkBox`/`ListBox` widgets | GTK signals call Rust closures sharing `Rc<Cell>` state |
| Slint | Declarative `.slint` boxes, properties and repeated rows | Rust models and callbacks update properties |
| Qt Widgets | C++ builds `QWidget`, `QVBoxLayout` and `QHBoxLayout` objects | Qt signals connect to C++ lambdas |
| Tauri | HTML panels, CSS Grid and persistent DOM buttons | JavaScript event handlers; Rust starts the system webview |

Egui declares panels and widgets inside `App::ui`; state updates sit beside click handling.
This example does not request continuous repainting. An excerpt from the
[complete Rust example](examples/egui/src/main.rs):

```rust
egui::Panel::left("yards").exact_size(210.0).show(ui, |ui| {
    ui.heading("Yards");
    if ui.button("All projects").clicked() {
        self.yard = 0;
    }
});
egui::CentralPanel::default().show(ui, |ui| {
    ui.heading("All projects");
    egui::ScrollArea::vertical().show(ui, |ui| {
        // Project buttons update self.project when clicked.
    });
});
```

GTK constructs a persistent widget tree and connects signals to closures. The
[gtk4-rs example](examples/gtk/src/main.rs) mirrors the earlier
[C control](examples/gtk-c/main.c) widget for widget:

```rust
let body = GtkBox::new(Orientation::Horizontal, 12);
let yards = GtkBox::new(Orientation::Vertical, 4);
let projects = ListBox::new();
let scroll = ScrolledWindow::new();
scroll.set_hexpand(true);
scroll.set_child(Some(&projects));
body.append(&yards);
body.append(&scroll);
projects.connect_row_selected(move |_, row| { /* update details */ });
```

These are shortened layout excerpts. The linked files contain the runnable applications.

### Slint: declarative widgets and Rust callbacks

The [layout](examples/slint/ui/main.slint) declares widgets and exposes callbacks;
[Rust](examples/slint/src/main.rs) supplies the filtered model and updates properties:

```slint
ListView {
    for project in root.projects: Button {
        text: project.name + "                 NOT_CREATED";
        height: 38px;
        checkable: true;
        checked: root.selected-project == project.id;
        clicked => { root.choose-project(project.id); }
    }
}
```

This stock Slint example explicitly selects winit/software and enables accessibility.
It does not import the four correctness forks used by the old Slint prototype.

### Qt Widgets: persistent C++ widgets and signals

The [C++ example](examples/qt/main.cpp) creates a widget tree and connects signals:

```cpp
auto *root = new QVBoxLayout(&window);
auto *body = new QHBoxLayout;
body->setSpacing(12);
auto *yards = new QWidget;
yards->setFixedWidth(200);
body->addWidget(yards);
auto *projectLayout = new QVBoxLayout;
auto *projects = new QListWidget;
projectLayout->addWidget(projects);
body->addLayout(projectLayout, 1);  // Expand the center column.
auto *details = new QLabel;
details->setFixedWidth(250);
body->addWidget(details);
root->addLayout(body, 1);
```

Qt Widgets uses native widget/layout APIs here; QML, Qt Quick and WebEngine are absent.

### Tauri: a web layout in a native system webview

The [HTML](examples/tauri/frontend/index.html) and
[CSS](examples/tauri/frontend/style.css) define the panels; ordinary DOM event handlers
in [JavaScript](examples/tauri/frontend/main.js) update the in-memory fixture:

```css
main {
    display: grid;
    grid-template-columns: 200px minmax(0, 1fr) 250px;
    gap: 12px;
}
```

```javascript
filter.addEventListener("input", updateFilter);
document.getElementById("all-projects").addEventListener("click", () => selectYard(0));
document.getElementById("refresh").addEventListener("click", () => {
  state.refreshes += 1;
  document.getElementById("snapshot").textContent = `Snapshot ${state.refreshes} · local fixture`;
});
```

There is no frontend framework, development server or application backend. Tauri uses
different system webviews on each OS, so a Windows result is not a WebKitGTK result.
See [Tauri's webview documentation](https://v2.tauri.app/reference/webview-versions/).

## Original matched Linux measurements — 2026-11-07

Original 1120×768 captures: [egui](screenshots/egui.png) and [GTK4](screenshots/gtk.png).
These historical results use the original source and renderer configuration.

One Debian 13 amd64 disposable VM, four logical CPUs, 4 GiB RAM, Xvfb/Openbox and
software rendering. Both examples ran sequentially on the same display and used the
same window size and data. Each phase settled for 30 seconds, then collected 120
samples over at least 120 seconds.

| Interface | Window | RSS median | PSS median | Idle CPU, one logical core |
| --- | --- | ---: | ---: | ---: |
| egui/eframe 0.37.0, Glow | Visible | 135.52 MiB | 116.26 MiB | 0.008% |
| egui/eframe 0.37.0, Glow | Minimized | 135.52 MiB | 116.25 MiB | 0.017% |
| GTK4 4.18.6 C, Cairo requested | Visible | 120.75 MiB | 95.27 MiB | 0 recorded ticks |
| GTK4 4.18.6 C, Cairo requested | Minimized | 120.75 MiB | 95.26 MiB | 0 recorded ticks |

GTK used **14.77 MiB less RSS** in this pair. Memory median, p95 and observed maximum
were identical within each phase. Both implementations were quiet when idle.

At the measured 100 Hz accounting rate, one CPU tick over 120 seconds is approximately
0.0083% of one core. Zero recorded ticks is below that resolution, not proof of zero
work. One or two ticks do not establish a significant CPU ranking.

Egui's actual OpenGL context reported Mesa llvmpipe software rendering. GTK was asked
to use Cairo; its internal renderer type was not instrumented. These are single-process,
UI-only results, excluding the X server, window manager and accessibility/session services.
They do not establish general toolkit memory floors, hardware-GPU performance or production
application costs. The [historical table](docs/historical-comparison.md) includes backend
processes and a different Wayland environment; its values are not directly comparable.

Read the [full methodology and verification](docs/methodology.md) or inspect the
[four raw sample sets](measurements/2026-11-07/README.md).

## Build and run

The commands below target Linux; the original `tools/measure.py` probe targets X11.
The separate [native runner guide](docs/github-runners.md) covers Windows/macOS and
the new examples. The original Debian measurements built the
[C control](examples/gtk-c/main.c) with GTK4 4.18.6. You need Rust/Cargo, Python 3, a C compiler,
`pkg-config`, GTK4 development libraries, and the X11/OpenGL development libraries.
The [reproduction guide](docs/methodology.md#reproduce) lists the Debian packages.

From this repository's root:

```sh
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$PWD/target}"
mkdir -p "$CARGO_TARGET_DIR"
cargo fmt --manifest-path examples/egui/Cargo.toml --check
cargo build --release --locked --manifest-path examples/egui/Cargo.toml
cargo build --release --locked --manifest-path examples/gtk/Cargo.toml
```

Launch one example at a time in a graphical Linux session:

```sh
"$CARGO_TARGET_DIR/release/veranda-egui-comparison"
# After closing egui:
"$CARGO_TARGET_DIR/release/veranda-gtk-comparison"
```

The binary name and GTK application ID retain the original experiment's names.
The examples require no Subyard installation, cache helper, account or service.
To reproduce the recorded software-rendering environment and sampling procedure,
follow [the measurement guide](docs/methodology.md#reproduce).

For the additional applications, follow their standalone instructions:
[Slint](examples/slint/README.md), [Qt Widgets](examples/qt/README.md), and
[Tauri](examples/tauri/README.md). Windows/macOS runner setup and GUI availability
checks are described in [the native runner guide](docs/github-runners.md).

## Adding another framework

Use the same data and controls, include a real screenshot and short layout excerpt,
and record the framework version, renderer, build mode and process scope. Compare
candidates in the same environment. Publish raw samples and distinguish a UI-only
experiment from an application with a real backend. Keep historical results separate
when the workload or environment differs.

Native-feature claims live in [`data/features.json`](data/features.json): add the
framework there with a source for every cell, then run
`python3 tools/render_features.py` to regenerate [docs/features.md](docs/features.md)
and the README summary. The [GitHub Pages site](https://heyvasily.github.io/rust-desktop-comparison/)
(`index.html` and `site/`) reads the same JSON and the measurement CSV directly.

The original Linux measurements were taken from [Subyard](https://github.com/subyard/subyard).
