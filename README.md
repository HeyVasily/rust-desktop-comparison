# Rust desktop GUI comparison

Small, inspectable desktop interfaces with **real screenshots, layout code and measured
resource use**. Runnable examples cover egui/eframe, GTK4, Slint, Qt Widgets and Tauri.
The original Linux measurements and later native runner results are kept in separate
series, with their process scope, renderer and platform recorded.

The examples show 10 synthetic yards and 100 projects: navigation, project selection,
scrolling, an editable filter and a Refresh button that advances an in-memory snapshot.
There is no backend, inventory scan or periodic polling. The original workload is named
Veranda; its labels are retained so the imported sources match the measured applications.

| Framework | Implementation here | Evidence |
| --- | --- | --- |
| egui/eframe 0.37.0 | [Rust example](examples/egui/src/main.rs), pinned dependencies | Screenshot and matched UI-only measurements |
| GTK4 4.18.6 | [C control](examples/gtk/main.c) | Screenshot and matched UI-only measurements; gtk4-rs is not measured |
| Slint 1.18.1 | [Stock Rust + declarative layout](examples/slint/README.md), winit/software | New native runs; [historical patched frontend](docs/historical-comparison.md) is separate |
| Qt Widgets | [C++17 + CMake example](examples/qt/README.md) | Installed Qt version recorded per run; [historical 6.8.2 frontend](docs/historical-comparison.md) is separate |
| Tauri 2.12.5 | [Rust + static HTML/CSS/JavaScript](examples/tauri/README.md) | WebKitGTK on Linux, WebView2 on Windows, WKWebView on macOS |

The three additional examples are new implementations of the same workload. Their
earlier full-backend measurements do not measure these new binaries. Native build,
screenshot and measurement outcomes are recorded by the
[GitHub runner diagnostic](docs/github-runners.md); adding source is not a passing run.

## What the interfaces look like

Actual 1120×768 captures of the running examples, with the same project selected and
snapshot 1 after Refresh. These illustrate the comparison workload, not a finished product.

### egui / eframe

![egui: yard navigation, project list, filter and selected project details](screenshots/egui.png)

### GTK4 control

![GTK4: the same synthetic data, controls and selected project details](screenshots/gtk.png)

### Additional interfaces on a macOS GitHub runner

These new examples were built and captured on macOS 15 ARM64. They show the initial
fixture state, project-001 and snapshot 0. Native window sizes differ because of the
hosted display; they are not the original Linux snapshot-1 captures above.

**Slint — declarative widgets with a software renderer**

![Stock Slint on macOS](screenshots/native-42412948217/macos-15/slint.png)

**Qt Widgets — native C++ widget tree**

![Qt Widgets on macOS](screenshots/native-42412948217/macos-15/qt.png)

**Tauri / WKWebView — embedded HTML/CSS/JavaScript**

![Tauri WKWebView on macOS](screenshots/native-42412948217/macos-15/tauri.png)

The [native results](docs/native-results.md) contain the full five-interface gallery,
raw-data links and memory/CPU observations. The Tauri screenshot establishes a useful
UI; its total macOS memory remains unknown because XPC helpers are outside the probe's
attributable scope. Linux uses WebKitGTK and Windows uses WebView2 instead.

## What the layout code looks like

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

GTK constructs a persistent widget tree and connects signals to callbacks. The
[C control](examples/gtk/main.c) uses this layout shape:

```c
GtkWidget *body = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 12);
GtkWidget *yards = gtk_box_new(GTK_ORIENTATION_VERTICAL, 4);
GtkWidget *scroll = gtk_scrolled_window_new();
projects = gtk_list_box_new();
gtk_widget_set_hexpand(scroll, TRUE);
gtk_scrolled_window_set_child(GTK_SCROLLED_WINDOW(scroll), projects);
gtk_box_append(GTK_BOX(body), yards);
gtk_box_append(GTK_BOX(body), scroll);
g_signal_connect(projects, "row-selected", G_CALLBACK(select_project), NULL);
```

These are shortened layout excerpts. The linked files contain the runnable applications.
The GTK control is written in C; these numbers do not measure Rust GTK bindings.

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
auto *projects = new QListWidget;
projects->setAccessibleName("Projects");
projects->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
QObject::connect(filter, &QLineEdit::textChanged, &window, [&](const QString &text) {
    updateFilter();
    std::cout << "filter " << text.toStdString() << std::endl;
});
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

## Matched measurements — 2026-11-07

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

The commands below and the original `tools/measure.py` probe target Linux/X11.
The separate [native runner guide](docs/github-runners.md) covers Windows/macOS and
the new examples. The original measured build used Rust/Cargo
1.99.1 and GTK4 4.18.6 on Debian 13. You need Rust/Cargo, Python 3, a C compiler,
`pkg-config`, GTK4 development libraries, and the X11/OpenGL development libraries.
The [reproduction guide](docs/methodology.md#reproduce) lists the Debian packages.

From this repository's root:

```sh
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$PWD/target}"
mkdir -p "$CARGO_TARGET_DIR"
cargo fmt --manifest-path examples/egui/Cargo.toml --check
cargo build --release --locked --manifest-path examples/egui/Cargo.toml
cc -O2 -Wall -Wextra -Werror examples/gtk/main.c \
    -o "$CARGO_TARGET_DIR/gtk-control" $(pkg-config --cflags --libs gtk4)
```

Launch one example at a time in a graphical Linux session:

```sh
"$CARGO_TARGET_DIR/release/veranda-egui-comparison"
# After closing egui:
"$CARGO_TARGET_DIR/gtk-control"
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

## Origin and license

The runnable sources, screenshots and measurements were imported from the
[Subyard comparison](https://github.com/subyard/subyard/blob/f0ff6f17f10cb9416fe3fe801a0b53b397bb5a14/docs/veranda/native-framework-comparison.md).
Source code and screenshot bytes are preserved. See [NOTICE](NOTICE.md) for provenance
and the original MIT notice, and [LICENSE](LICENSE) for this repository's MIT license.
