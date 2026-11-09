# Measurement method

There are separate datasets and build profiles in this repository. The current
comparison is a **desktop-integrated baseline**; older measurements remain bound
to their original source, features, runtime and workload. Adding an integration
or changing a toolkit/plugin version does not retroactively change those results.
See also the [desktop profile and acceptance contract](desktop-integration.md)
and [native runner procedure](github-runners.md).

## Current desktop measurement contract

All five applications show the same synthetic ten-yard, 100-project interface,
with selection, scrolling, an editable filter and an in-memory Refresh counter.
There is no backend, disk inventory or periodic data refresh. The intended
window is 960×640 logical pixels; Linux/Windows probes also verify the requested
physical client dimensions. macOS captures include the titlebar and must not be
described as equivalent client-only geometry.

The primary build must include normal desktop text and appearance integration:

| Candidate | Current profile | Important cost/scope distinction |
| --- | --- | --- |
| egui | eframe `desktop` default: OS clipboard, link opening, system-font fallback, AccessKit, existing renderers/backends, Linux Settings portal observer | Its former explicit feature list disabled OS clipboard, links and system fonts; a lockfile entry alone does not prove an enabled feature |
| GTK | GTK4 + libadwaita, initialized with system-following StyleManager | Native libadwaita is a real dependency; this is not the historical bare-GTK build |
| Slint | Existing winit/software widget setup and accessibility integration | Keep these enabled; validate the actual widget/backend rather than infer behavior from the API |
| Qt Widgets | Modern Qt with native platform integration; Linux GNOME profile uses Qt 6.8.3 and its matching GTK3 platform-theme plugin | GTK3 and QtDBus loaded in the Qt process count toward memory; old Qt 6.4/generic-theme measurements do not describe this setup |
| Tauri | System webview with the application's light/dark CSS and normal editable control | Attribute webview helper processes; do not compare only the launcher process |

Qt's GTK3 theme plugin and its Qt kit must match. A distribution plugin must not
be inserted into a different downloaded kit. The Linux profile must have a
working Settings portal/backend in the same graphical session. KDE or other
desktop integrations are separate environments with their own matching plugins,
not evidence of a universal GNOME result. Record the exact native library and
plugin versions as well as Rust crate versions.

### Acceptance comes before idle sampling

Run `tools/native_probe.py` with `--desktop-checks` in a **disposable desktop
session**. The check changes OS appearance and overwrites the system clipboard
with synthetic text. It restores the appearance setting and stops its helpers;
it does not restore arbitrary original clipboard formats or ownership. Do not
run it unattended on a user's working desktop.

For a primary result, the probe must:

1. Set and independently read the OS appearance preference before launching the
   app; on Linux verify the Settings portal value, not just `gsettings` success.
2. Capture the actual client after startup and establish the requested palette.
3. Keep the same application process and window alive through light → dark →
   light, or the reverse for a dark-start supplemental check. Capture both
   transitions and verify a substantial change in client luminance. No forced
   application palette, process relaunch or periodic application polling is an
   acceptable substitute for system-driven integration.
4. Seed Unicode text from an external process, paste it into the ordinary filter
   with Ctrl/Cmd+F and Ctrl/Cmd+V, replace the OS clipboard with a different
   sentinel, then copy the filter back and compare the externally read text
   exactly. The sentinel prevents an ignored copy operation from passing on the
   old clipboard contents.
5. Clear the filter, move focus away from the editor, park the pointer, return to
   the initial appearance and stop probe-owned clipboard helpers. Retain the
   restored-fixture screenshot before settling and measuring.

The acceptance gate writes `desktop-integration.json`, screenshots and an embedded
`desktop_integration` outcome. It distinguishes `passed`, `failed`, `not_run` and
`environment_error`. Missing evidence is never a pass. A primary idle comparison
is refused when mandatory checks fail; cleanup and process-scope failures also
exclude the result from a primary summary. Nonuniform screenshots and luminance
thresholds are automated checks, not complete visual proof: inspect the captures
for a wrong UI, titlebar-only changes or occlusion.

The Linux automated keyboard/clipboard driver currently covers **X11**, not
native Wayland. An XWayland window is not native-Wayland acceptance. A missing
driver, graphical session, portal or permission is an environment/coverage gap,
not evidence that the toolkit lacks the capability.

### Sampling, process scope and metrics

After acceptance, the native probe performs a short diagnostic phase, then
`--comparison` uses 30 seconds of settling and 120 one-second sample intervals.
Candidates run sequentially, not simultaneously. Linux additionally records an
explicitly separate minimized phase with X11 visibility/state verification.
Repeat on fresh runners to expose run-to-run variance; publish each repetition,
not only the best result or an average with failures removed silently.

The process-family scope includes the application and attributable helpers,
including webview subprocesses. macOS WKWebView attribution uses the recorded
responsibility scope in addition to ancestry. Preserve process identity and
report access failures, unattributed helpers, late-discovered processes and
cleanup survivors. An incomplete scope is not a valid small memory result.

| OS | Primary memory metric | Interpretation |
| --- | --- | --- |
| Linux | PSS from process accounting | Shared pages apportioned by mapping count |
| Windows | Private working set | Resident private pages; shared pages excluded |
| macOS | Physical footprint | macOS's attributable memory-accounting metric; not Linux PSS |

Also publish summed RSS/Working Set and the metric name. Summed resident sets can
double-count shared pages. These primary metrics are **not directly comparable
across operating systems**; compare candidates within the same OS, runtime and
rendering environment. CPU is observed process user+system time normalized to one
logical core. Zero ticks means below the interval's accounting resolution, not
zero work, and tiny tick differences do not justify a CPU ranking.

Threads, font caches and in-process libraries for the integration are part of
the application measurement. The compositor/X server, session bus, shared
Settings portal and probe are outside that process family. Name these required
services and any newly started helpers instead of treating their exclusion as a
claim of zero system cost. This remains a small backend-free desktop baseline,
not a production application's total resource budget.

### Reduced control and attribution

`egui_reduced` is an explicit **diagnostic-reduced** candidate, built from the same
source and lockfile with `--no-default-features` into a separate target directory.
It is not the normal desktop application and must never replace `egui` in a
primary ranking. Its missing external clipboard/portal path is deliberate; do
not waive primary acceptance and then silently present it as an equivalent app.

For an integration delta, pair reduced and integrated runs on the **same runner,
repetition, source revision, compiler, display session and renderer**. Keep font
installation, final light palette, fixture state, geometry and sampling policy
fixed, alternate run order, and publish the paired raw medians/ranges and idle
CPU. Verify the reduced control's light OS preference before and after sampling;
this prerequisite does not claim application-theme or clipboard acceptance.

The warmed workloads are **not identical**. The integrated candidate is measured
after external clipboard and live system-theme use; the reduced candidate cannot
exercise those capabilities. The delta measures the whole configured profile
after use, including retained caches/allocations, not a clipboard-only or
theme-only allocation. This is a controlled profile comparison, not a fully
equivalent-product contest or a feature-isolation experiment.

Retain diagnostic controls separately from the primary summary. An old hosted
runner result and a new local build do not form a matched pair. Enabling more
dependencies can change code, caches, threads and shared pages, but neither the
dependency count nor executable-size growth determines the resident-memory
delta. Report what was measured without assuming either a large increase or a
negligible one.

### Provenance and interpretation limits

Retain source commit, Cargo.lock, target-specific enabled feature tree,
toolchain/native-library/plugin versions, binary SHA-256 and size, runner image,
display backend and actual renderer, acceptance evidence, process scope and raw
samples. Feature configuration, build success, API availability and behavioral
acceptance are distinct claims. Historical rows missing modern profile/evidence
fields stay historical; an importer must not upgrade them to desktop passes.

The Linux CI display is **X11/Xvfb with software rendering (Mesa llvmpipe)**, not
a real native-Wayland session or hardware-GPU benchmark. The pinned/profile
changes do not make old software-rendered data representative of a laptop GPU.
The [historical X11/Wayland series](linux-display-comparison.md) and
[GTK renderer experiment](gtk-memory-investigation.md) remain separate datasets.
Startup latency, interactive frame rate, full IME/font/screen-reader behavior,
tray/global-shortcut integrations, clipboard images/MIME/persistence and
backend-connected production load require additional checks/profiles.

## Current desktop-profile reproduction

Use the [native comparison workflow](../.github/workflows/native-comparison.yml)
as the complete platform/dependency recipe. On Linux, build dependencies now
include GTK4 **and libadwaita**, plus the chosen Qt kit and matching GTK3 theme
plugin when testing Qt. The graphical session needs an X11 display/window
manager, session D-Bus, Settings portal/backend, GNOME settings schemas,
`gsettings`/`gdbus`, `xdotool`, X11 utilities and an external clipboard helper.
The probe requires the pinned Python packages recorded in the workflow.

Build the normal egui profile and capture its resolved feature graph:

```sh
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$PWD/target}"
mkdir -p out/desktop-build
cargo build --release --locked --manifest-path examples/egui/Cargo.toml
cargo tree --locked --manifest-path examples/egui/Cargo.toml -e features \
  > out/desktop-build/egui-features.txt
```

Inside a prepared **disposable X11 desktop session**, from the repository root:

```sh
python3 tools/native_probe.py \
  --name egui --title 'Veranda egui comparison' \
  --executable "$CARGO_TARGET_DIR/release/veranda-egui-comparison" \
  --output out/desktop-egui-light \
  --desktop-checks --startup-theme light --comparison --client-size 960 640
```

This launches and cleans up the app itself. Use a separate output directory and
`--startup-theme dark` for the supplemental dark-start case. For macOS omit
`--client-size`; the probe cannot validate a client-only size from Quartz outer
bounds. Use the matching executable/title and platform prerequisites for another
candidate; see the workflow rather than inventing a wrapper or title match.

Build the egui control without overwriting the normal executable:

```sh
CARGO_TARGET_DIR="$PWD/target/egui-reduced" \
  cargo build --release --locked --no-default-features \
    --manifest-path examples/egui/Cargo.toml
```

Keep its run labeled `egui_reduced` and diagnostic-only, with separate evidence
and the same-host pair identity. A command without `--desktop-checks` does not
qualify as a desktop-integrated result. Do not compare it to unrelated historical
medians to claim integration overhead.

## Historical baseline: original 2026-11-07 Linux pair

Everything below describes the archived original egui/GTK experiment, not the
current defaults. Check out the recorded revision before using its commands.
The five-candidate 2026-11-09 matrix is documented separately in
[full native results](full-native-results.md); that series also predates the
desktop acceptance profile.

### Recorded environment

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

### Workload and process scope

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

### Verification and provenance

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

### Reproduce

Use a quiet disposable Linux VM for graphical workloads. On Debian 13, the packages are:

```text
build-essential pkg-config libgtk-4-dev libxkbcommon-dev libegl1-mesa-dev
libgl1-mesa-dev libx11-dev libxi-dev libxrandr-dev libxcursor-dev xvfb openbox
xdotool x11-utils imagemagick mesa-utils dbus
```

At the archived `d1a45eb` source, build using that revision's root instructions,
then, from the repository root, export paths before starting the session bus:

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
