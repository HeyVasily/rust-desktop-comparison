# Measurement method

This page describes the original egui/GTK Linux pair. The new Slint, Qt Widgets
and Tauri implementations use the separate [native runner procedure](github-runners.md).
Their build and measurement outcomes must be recorded per run; they do not inherit
the historical results below.

## Recorded environment

The 2026-11-07 matched comparison used one disposable Debian 13 amd64 VM with four
logical CPUs, a 4 GiB RAM allocation and 20 GiB disk. Xvfb `2:21.1.16-1.3+deb13u4`
provided a 1920×1080×24 X11 display; Openbox was `3.6.1-12+b2`, with no compositing
manager. Both client windows were 1120×768.

Both applications inherited `LIBGL_ALWAYS_SOFTWARE=1`, `GDK_BACKEND=x11` and
`GSK_RENDERER=cairo`. Egui selected Glow; its actual context reported
**llvmpipe (LLVM 19.1.7, 256 bits)**, with Mesa `25.0.7-2+deb13u1`.
GTK `4.18.6+ds-2` was requested to use Cairo; its internal renderer was not instrumented.

Rust/Cargo 1.99.1 built the release executable from pinned eframe 0.37.0 and the
checked-in lockfile. Enabled eframe features are `accesskit`, `default_fonts`,
`glow` and `x11`; `wgpu`, `wayland` and `persistence` are disabled. Dependencies are
unpatched. The GTK4 C control used `cc -O2 -Wall -Wextra -Werror`.

## Workload and process scope

Both examples contain 10 synthetic yards and 100 project rows. Selection, filtering,
scrolling and Refresh operate only on in-memory data. Refresh advances a snapshot
counter; it does not query a backend. Before sampling, the apps displayed All projects,
an empty filter, project-004 selected and snapshot 1. Screenshots were taken before
measurement; text entry was unfocused and the pointer moved out of the window.

Applications ran sequentially. Each visible/minimized phase settled for 30 seconds
and then collected 120 samples over 120.34–120.37 seconds, plus a CPU baseline.

The [probe](../tools/measure.py) counts the GUI process and all its threads. It refuses
child processes, checks stable PID/start time, and verifies X11 mapped/hidden state
before and after each phase. Failed reads abort rather than inventing samples.
Xvfb, Openbox, session/accessibility services, input tools and the probe are excluded.

RSS and PSS are read from `/proc/PID/smaps_rollup`; p95 uses nearest rank. CPU is the
process user+system tick delta divided by monotonic elapsed time, normalized to one
logical CPU. At 100 Hz, one tick over the measured interval is about 0.0083% of one
core. Egui accumulated one visible and two minimized ticks; GTK accumulated zero.
These small counts do not establish a significant CPU ranking.

Across the four phases, guest CPU idle time was 99.915–99.925%, steal was
0.0021–0.0042%, and CPU PSI `some avg10` was 0.00%. These observations cannot establish
absence of external physical-host load. This is one bounded run, not an estimate of
variance across machines or renderers.

## Verification and provenance

Release/locked Rust builds, formatting and the C warning-as-error build passed.
Real pointer/keyboard navigation, selection, scrolling, filter editing/restoration,
Refresh, screenshots and natural closure passed for both measured binaries. Each
of the four phases had 120 valid samples without missing reads or identity/state
failures. Both applications exited naturally with status zero; VM release succeeded.
Independent review recomputed the summaries and checked source/screenshot bindings.

The [raw samples](../measurements/2026-11-07/README.md) are copied from the original
run. At comparison repository commit `d1a45eb`, the imported examples and probe
were byte-identical to Subyard commit `f0ff6f17f10cb9416fe3fe801a0b53b397bb5a14`.
Later native-runner fixtures use 960×640 windows and Windows-specific rendering;
those changes do not alter this original dataset. Check out `d1a45eb` to reproduce
the original source and commands below.

Original measured binary SHA-256 values:

- egui: `ccc460af5c013bf7e503a174f4c63bc95dd5cb4d07018f7c9a2a26aeae547948`
- GTK: `346e4248b5a35479b079e57ef62d404755e11fa0e032e504f1fbd9c2d85f92e2`

The original source-manifest digest is
`430a7abf3fdc7ee109e63f8d56ca9c85e9831fa2d97558d3bd0aeb15337e4cf9`.
It includes the original file names and is not a digest of this relocated tree.
See [NOTICE](../NOTICE.md) for the exact original paths.

Hardware GPU behavior, other platforms, gtk4-rs integration, production accessibility/
IME, real-backend costs, startup latency and full application acceptance are not
established by this small comparison.

## Reproduce

Use a quiet disposable Linux VM for graphical workloads. On Debian 13, the packages are:

```text
build-essential pkg-config libgtk-4-dev libxkbcommon-dev libegl1-mesa-dev
libgl1-mesa-dev libx11-dev libxi-dev libxrandr-dev libxcursor-dev xvfb openbox
xdotool x11-utils imagemagick mesa-utils dbus
```

Build using the [root instructions](../README.md#build-and-run), then, from the repository
root, export paths before starting the session bus:

```sh
export COMPARISON_ROOT="$PWD"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$PWD/target}"
dbus-run-session -- bash
```

Inside that child shell:

```sh
cd "$COMPARISON_ROOT"
mkdir -p out
export DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1 GDK_BACKEND=x11 GSK_RENDERER=cairo
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp >out/xvfb.log 2>&1 &
xvfb_pid=$!
sleep 2
openbox >out/openbox.log 2>&1 &
openbox_pid=$!
sleep 2
"$CARGO_TARGET_DIR/release/veranda-egui-comparison" >out/egui.log 2>&1 &
app_pid=$!
```

First exercise the controls. Restore All projects, empty filter and project-004,
click Refresh once, unfocus the text entry and move the pointer outside. Obtain
the visible application window with PID **and** title matching; GTK also has a hidden
helper window, so PID-only or OR searches can select the wrong window.

```sh
window=$(xdotool search --onlyvisible --all --pid "$app_pid" --name 'Veranda')
xwininfo -id "$window"  # Verify the actual 1120x768 application window.
import -window "$window" out/egui.png
python3 tools/measure.py --pid "$app_pid" --window "$window" \
    --state visible --output out/egui-visible.json
xdotool windowminimize "$window"
python3 tools/measure.py --pid "$app_pid" --window "$window" \
    --state minimized --output out/egui-minimized.json
```

Restore the window with `xdotool windowmap "$window"`, close it normally using the
window manager, and run `wait "$app_pid"` to check its exit status. Then launch
`"$CARGO_TARGET_DIR/gtk-control" >out/gtk.log 2>&1 &`, record its PID, and repeat the
same controls/capture/phases using `gtk` output names. Keep the same X server,
window manager, font/DPI settings and window size. Do not measure both apps concurrently.

After both apps close, stop the owned display processes with
`kill "$openbox_pid" "$xvfb_pid"` and reap them with `wait "$openbox_pid" "$xvfb_pid"`.
Keep the raw samples, versions, source/binary hashes and screenshots before releasing
the VM. Check pressure and competing load instead of interpreting an oversubscribed
VM's CPU figures as framework behavior.
