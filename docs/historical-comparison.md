# Historical Qt Widgets, GTK4 and Slint comparison

These results were measured on **2026-10-10** for Subyard's Veranda frontend.
They include a real local backend and use a Wayland environment. They are separate
from the [2026-11-07 synthetic UI-only comparison](../README.md#original-matched-linux-measurements--2026-11-07).
Qt and Slint prototype sources and screenshots are not included in this repository.

## Results

Memory is median MiB. CPU is the average percentage of one logical CPU over the
entire desktop scope. Memory median, p95 and observed maximum were identical in
each candidate's visible and minimized windows.

| Candidate | UI RSS | Desktop RSS | Desktop PSS | Visible CPU | Minimized CPU |
| --- | ---: | ---: | ---: | ---: | ---: |
| Slint 1.18.1, patched software renderer | 35.00 | 62.48 | 55.86 | 0.050% | 0.083% |
| Qt Widgets 6.8.2, system libraries | 51.91 | 86.93 | 76.03 | 0.050% | 0.108% |
| GTK4 4.18.6 C, Cairo renderer | 41.98 | 76.72 | 62.11 | 0.008% | 0.017% |

Slint's desktop scope contained its UI and local Go RPC process. Qt and GTK also
used the same native Rust bridge. Each process was counted once; summed RSS counts
shared pages in each process. PSS was reported separately. Compositor, input/resource
probes, fixture, Incus and external workloads were outside the scope.

Slint had the least measured memory; GTK had the least measured idle CPU and used
unpatched system libraries. These single bounded runs do not establish across-machine
statistics or the footprint of the eventual gtk4-rs application. The GTK frontend
was C, Qt was C++, and Slint used Rust.

## Method

The workload contained 10 yards and 100 projects in total, with authoritative
inventory/details, all projects `NOT_CREATED`, explicit Refresh and no periodic
polling or event generator. Each native UI displayed real responses from the same
Rust/Go backend. The local Go process in the Slint run used about 27.47 MiB RSS.

The environment was Debian 13 amd64, four logical CPUs, 8 GiB RAM, a 40 GiB disposable
VM, labwc 0.8.3 with Pixman, no Xwayland, 1920×1080 at 60 Hz/scale 1, and an 1120×768
application window. Slint used software Wayland rendering; Qt used its Wayland platform;
GTK used Wayland/Cairo. Packages were Qt base `6.8.2+dfsg-9+deb13u2`, Qt Wayland
`6.8.2-4`, GTK `4.18.6+ds-2`, and AT-SPI `2.56.2-1+deb13u2`. Slint used Rust 1.92.0.

Each exact build passed useful launch, real selection/scrolling, Unicode input and
restoration, physical Refresh, natural closure and cleanup before measurement.
Runs were sequential: 30 seconds settling, then at least 120 seconds and 120 samples
for each visible/minimized state. Identities were stable, process/PSS samples were
complete, and memory sums were recomputed from retained raw samples. App-cgroup
pressure counters were zero; root-cgroup pressure telemetry was unavailable.

## Why the current Linux numbers differ

The current runner table measures newly implemented, backend-free demos. It does
not repeat the historical frontend experiment. These are all RSS values in MiB;
PSS must not be substituted for either RSS column:

| Framework | Historical GUI RSS | Historical GUI + backend/bridge RSS | Current Linux demo RSS |
| --- | ---: | ---: | ---: |
| Slint | 35.00 | 62.48 | 22.99 |
| Qt Widgets | 51.91 | 86.93 | 33.60 |
| GTK4 C | 41.98 | 76.72 | 240.27 |

The historical desktop scope had two processes for Slint and three for Qt/GTK.
The new Qt/GTK/Slint cases each have one GUI process and no Go backend or Rust
bridge. Even the GUI-only columns describe different frontend implementations,
models and integrations, rather than the same binaries with their backend removed.
Historical Slint also used the correctness forks described below; their memory
effect was not established.

The old environment was Debian/Wayland/labwc/Pixman, with GTK explicitly using
Cairo. The new environment is Ubuntu/X11/Xvfb/Openbox. It requests software OpenGL,
but **does not set `GSK_RENDERER` or record GTK's selected renderer class**. Egui's
llvmpipe log does not establish GTK's renderer. GTK changed from 4.18.6 to 4.14.5,
Qt from 6.8.2 to 6.4.2, and the client size from 1120×768 to 960×640. The new GTK
log also reports an unavailable accessibility bus, so the integration environment
differs as well.

A changed GTK rendering path is a possible contributor to its larger footprint,
not a measured allocation breakdown. The separate imported Cairo/X11 UI-only GTK
run already measured **120.75 MiB RSS / 95.27 MiB PSS**, rather than the historical
Wayland GUI's 41.98 MiB RSS. See the [original methodology](methodology.md) and
[raw sample](../measurements/2026-11-07/gtk-visible.json).

The existing data cannot isolate the memory cost of the renderer, display backend,
library version or frontend code. That requires a controlled run of the same
binary/environment with the renderer recorded and varied independently. The new
numbers describe their recorded demo configurations; they do not establish a GTK
regression or reverse the historical project decision. Historical CPU covers the
desktop process scope; current CPU covers only each demo family, with tiny idle
increments subject to counter resolution.

## Maintenance caveats

The Slint result included four local correctness forks: `accesskit_unix` 0.22.1,
`accesskit_atspi_common` 0.19.1, `i-slint-core` 1.18.1 and `i-slint-backend-winit` 1.18.1.
They addressed AT-SPI signal encoding, disabled accessibility states, aggregate keyboard
modifiers and complete software frame repainting. Stock Slint behavior/footprint was
not qualified; a memory benefit from the patches was not established. Qt/GTK system
libraries were unpatched.

The original project selected GTK4/gtk4-rs on 2026-10-11. That was a project decision
based on its requirements, not a universal framework recommendation. Later application
qualification, real workloads, latency, accessibility/IME, other platforms and delivery
were separate requirements.

The retired Tauri/WebKitGTK frontend had also been measured at roughly 500–600 MiB
RSS in different environments. Its [original historical reference](https://github.com/subyard/subyard/blob/f0ff6f17f10cb9416fe3fe801a0b53b397bb5a14/docs/veranda/webview-memory-reference.md)
describes those runs; it is not part of either matched comparison here.

Source: [the original source-bound comparison](https://github.com/subyard/subyard/blob/f0ff6f17f10cb9416fe3fe801a0b53b397bb5a14/docs/veranda/native-framework-comparison.md#historical-results-2026-10-10).
The historical raw artifacts and temporary prototype bundles were retained with the
original project; this repository imports the documented results, not those binaries.
