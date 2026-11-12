# Native desktop diagnostics on GitHub-hosted runners

The [workflow](../.github/workflows/native-comparison.yml) builds release examples
and attempts real desktop acceptance and GUI sampling on Windows, macOS and
Linux X11. Its defaults request all three operating systems, three independent
repetitions, the desktop-integrated profiles, full memory/CPU sampling, a separate
reduced egui control, and an additional dark-startup check in every repetition.
This page describes the current procedure, not a claim that its newest runs passed.
The [desktop-integrated baseline](desktop-integration.md) defines the profile;
the [2026-11-09 results](full-native-results.md) retain the historical UI-only
procedure and source revision.

The `platforms` input supports `native` (Windows and macOS), individual `windows`,
`macos` or `linux` (`ubuntu-24.04`), and `all`. The optional `framework` input
accepts `all` or a comma-separated subset such as `gtk,slint` for focused retries.
`all` remains the default. A subset run validates only those candidates, and its
title/artifacts identify that scope. Empty, duplicate and unknown selections fail
before SDK setup. `egui_reduced` is not an accepted primary-framework name: the
`reduced_control` option adds it separately only when egui is selected.
Each OS/repetition job runs its candidates sequentially on one runner, with at
most nine jobs running concurrently. A successful build alone establishes neither
GUI access nor desktop acceptance.

The configured runner labels are `windows-2022`, `macos-15` and `ubuntu-24.04`.
Image contents change; artifacts record the image version, OS, architecture, CPU,
memory, Rust compiler and native library versions. See the official
[runner image inventory](https://github.com/actions/runner-images#available-images).
Different operating systems, architectures, source revisions and build profiles
must be analyzed separately. Image changes require fresh acceptance and sampling.
A hosted image rollout can give repetitions of the **same workflow run** different
image versions. Keep those groups separate and report each group's actual `n`;
the requested repetition count is not an observed sample count. Every repetition
includes its own dark-startup evidence so no group borrows acceptance from another
image.
The probe uses the captured Python 3.12 executable throughout the job, including
child processes; tool installers can otherwise change which `python` is on `PATH`.

## Starting a run

In Actions, select **Native desktop comparison**, then **Run workflow**. Set
`comparison` to false for an acceptance smoke run without the 120-interval ranked
idle phases. Startup appearance, live appearance changes and external clipboard
acceptance remain enabled. `appearance` requests the additional dark-startup case;
`reduced_control` requests the separately labeled egui A/B control.

Development branches also have an explicit opt-in push route. A push to `codex/**`
must change a watched path (`examples/**`, `tools/**` or the native workflow) and
include one of these markers in the head commit message:

- `[desktop-smoke]`: one repetition per selected OS, desktop acceptance and short
  diagnostics, but no ranked 120-interval measurements.
- `[desktop-benchmark]`: three fresh VMs per selected OS, acceptance and full
  footprint sampling.
- An additional `[windows-only]`, `[macos-only]` or `[linux-only]` narrows either
  route to that OS; without one, all three OSes are configured.
- An additional `[gtk-only]` selects GTK alone for focused desktop-driver
  diagnostics. Its title, build steps and verification gates retain that subset;
  it is not a complete five-candidate comparison.

Ordinary pushes do not start the expensive desktop jobs. The workflow has only
`contents: read` permission. An opt-in marker requests a run; it is not passing
evidence. Check the uploaded outcomes and final verification gates.

## Repetitions, memory metrics and desktop acceptance

`repetitions` (1, 3 or 5; default 3) runs every OS job that many times, each on a
fresh runner VM, so VM-to-VM variation and outliers become visible. Artifacts are
named `native-<runner>-<run-id>-r<k>`.

Each sample records, per process, RSS/Working Set and an OS-specific primary
metric: Linux PSS (`/proc/<pid>/smaps_rollup` via psutil), macOS
`phys_footprint` (`proc_pid_rusage`, Activity Monitor's *Memory*) and the Windows
private working set (psutil USS, Task Manager's *Memory*). Executable sizes are
recorded in `build/binary-sizes.json`.

Before sampling a normal candidate, the driver establishes and independently
reads the real OS light preference, launches the application, checks the client
palette, and changes light → dark → light in the same live process/window. It
then pastes synthetic Unicode text from the external OS clipboard into the
ordinary filter, replaces the clipboard with an unrelated sentinel, copies from
the filter, and checks the externally read text exactly. An ignored copy therefore
cannot pass by returning the original seed. The filter is cleared, focus and pointer
are moved away, and probe-owned clipboard helpers are reaped before settling and
idle sampling. Integration resources in the application remain enabled and counted.

Windows changes and reads the user appearance settings and broadcasts
`WM_SETTINGCHANGE`; macOS uses the system appearance preference. Linux uses the
explicitly named `gnome-adwaita-dual-preference-v1` session profile: it changes the
shared `color-scheme` and legacy `gtk-theme` preferences together (`prefer-light`
with `Adwaita`, or `prefer-dark` with `Adwaita-dark`). This applies to every candidate and
the control, not a Qt-only/app-specific palette override. The driver independently
reads both the Settings portal and the effective GTK3/XSettings `gtk-theme-name`
through `gtk-query-settings`; mismatches refuse acceptance. Both original
preferences are restored. This controlled Adwaita setup is not a claim that every
GNOME version or Linux desktop synchronizes legacy themes identically.
A setting label, painted titlebar or successful
`gsettings` exit is not sufficient: captures and client-luminance changes are
retained. A missing portal, permission or supported input driver is recorded as
an environment/coverage problem, not proof that a framework lacks the feature.

With `appearance` enabled, every repetition additionally launches each primary
candidate under an already-dark OS setting in `artifacts/dark/`, then checks
dark → light → dark and the same external clipboard path. This is a separate
acceptance/diagnostic run, not another ranked idle sample. Both the normal and
dark-startup verification gates must pass for the complete job to pass. A valid
light-state memory sample remains evidence for that invocation if the separate
dark-startup case fails; do not describe the overall desktop acceptance as passed.
The old `appearance-summary.json` belongs to historical relaunch-only runs.

These tests deliberately replace the clipboard and change global appearance.
Run them only in disposable CI/test desktops, never an active personal session.
Original appearance is restored and restoration failures invalidate acceptance;
previous private clipboard content/format ownership is not captured or restored.

## Run evidence and failure handling

The probe waits up to 45 seconds for an owned window with the expected title.
It then allows up to 30 seconds for a nonblank, correctly themed first client
frame. A mapped webview window is not necessarily a rendered page. The same
startup budget applies to every candidate; same-process live palette changes
retain a separate eight-second deadline. Captures record attempts, elapsed time
and the applied budget, without treating a blank window as a light-theme pass.
After successful desktop acceptance, the short diagnostic settles for five
seconds, waits up to 45 additional seconds for a nonblank client capture, records
ten sampling intervals and captures the window again. Each candidate has a
540-second watchdog; the job has a 120-minute limit including compilation.

Inspect downloaded `native-<runner>-<run-id>-r<k>` artifacts before interpreting results:

- `build/`: compiler/native library versions, build logs, executable sizes/hashes,
  copied committed Cargo lockfiles, and resolved `cargo tree --locked -e features`
  outputs for the selected profiles. Rust formatting uses `cargo fmt --check`;
  CI does not reformat sources or regenerate locks. `source-commit.txt`
  and the sorted `source-sha256.txt` identify the exact tracked examples, probes
  and workflows. Source recording runs before and after builds and refuses dirty
  tracked benchmark inputs. Native versions and feature graphs, including GTK's
  separate MSYS2 build, must be reviewed with the source revision.
- `<candidate>/outcome.json`: actual outcome, window owner/title/bounds, capture dimensions,
  environment, `measurement_profile`, requested comparison, process scope,
  limitations, summary and cleanup status. A failed acceptance may have no phases.
- `<candidate>/desktop-integration.json` and `desktop-*.png`: startup/live palette
  evidence, process/window identity, observed OS settings, external clipboard
  results and restored fixture. Top-level pass labels alone are insufficient.
- `egui_reduced/control-system-theme.json`: the control's independently checked
  before/after light OS preference and restoration, not desktop acceptance.
- `<candidate>/application.log`: stdout/stderr, including an observed renderer when the
  application reports one. A configured renderer is not proof of the renderer in use.
- `<candidate>/diagnostic*.png`: real OS captures. Inspect for the intended interface,
  clipping, blank content, occlusion and correct initial fixture state. These captures
  show each example's initial UI state; they do not reproduce the historical Linux snapshot-1 interaction.
  In particular, the original controls and new examples differ in initial selection.
- `<candidate>/*-samples.json`: raw timestamps, process identities, CPU counters,
  RSS/Working Set and the per-platform primary memory metric.
  Samples are written incrementally so a later failure retains earlier observations.
- `dark/<candidate>/`: separate dark-startup acceptance, captures and diagnostic
  outcome. `failed-candidates.json`, `stopped-after.json`, `watchdog.json` and
  runner-error evidence explain incomplete or refused comparisons when applicable.

Enable `comparison` for 30 seconds of settling followed by 120 sampling intervals.
Each interval includes one second of delays plus process-monitoring overhead; actual
elapsed time is retained and used for CPU normalization. For normal desktop
candidates this phase runs only after acceptance, diagnostic and scope checks
pass. Windows/macOS measure visible idle state only. Linux additionally minimizes the
window, verifies both `_NET_WM_STATE_HIDDEN` and `IsUnMapped`, and repeats the settling
and 120-interval phase with the minimized state verified again afterward. This is
post-exercise idle memory/CPU, not interaction latency, throughput or lifetime peak
memory. A failed candidate remains a failed job after artifacts upload. All five
primary candidates are configured on each OS, including GTK4 plus libadwaita through MSYS2 UCRT64 on
Windows. Its controlled Windows variant also sets `GTK_CSD=0`, using native window
decorations so the client capture excludes GTK titlebar/shadow pixels. Other configured examples are attempted even if an earlier build
or diagnostic fails, provided cleanup is explicitly clean or no process was launched.
Missing/unknown cleanup status, survivors or denied process access stop subsequent
candidates. An overall watchdog expiry also stops subsequent candidates to avoid
contaminating their measurements.

## Reduced control and importing results

The separately named `egui_reduced` executable uses `--no-default-features`. It
retains the selected renderer, display backends, bundled fonts and accessibility,
but omits the default desktop feature bundle. It is not a primary candidate.
The runner puts this control before egui in odd repetitions and after egui in even
repetitions. Its OS setting is established as light and read again after sampling;
missing prerequisites or failed restoration invalidate the control and stop later
candidates. This control does not pass or claim system-clipboard/live-theme
acceptance. The desktop profile is measured after those real operations; the
paired delta is the configured-profile difference, not clipboard-only allocation.

`python tools/import_native_run.py RUN_ID ARTIFACT_DIR SERIES` preserves raw
evidence under `measurements/native-<run-id>/r<k>/<runner>/`, including all desktop
captures, dark-startup repetitions, build evidence and deterministic gzipped
samples. Repetition-1 overview images also retain the historical
`screenshots/native-<run-id>/<runner>/` layout. Under `measurements/<series>/` it writes:

- `runs.csv`: measured phases and failed requested comparisons, including
  measurement/acceptance profiles and exclusion reasons.
- `summary.csv`: eligible primary desktop results and separately identified
  historical rows; no reduced controls. Medians of repetition medians, min/max,
  spreads and repetitions more than 10% from the median remain available.
- `controls.csv`: eligible reduced diagnostic controls only.
- `desktop-acceptance.csv`: normal and separate dark-startup outcomes.
- `paired-egui-ab.json`: raw matched desktop/control rows and deltas for the same
  run, runner, repetition, source/build identity, image and memory metrics.
- `import-report.json` and `SHA256SUMS`: import status, exclusions and report checksums.

New primary rows need `comparison_passed`, clean process cleanup, 120 complete
intervals and complete matching desktop evidence. Missing/failed checks do not
become zero-memory results. If none qualify, `summary.csv` has headers but no
ranking rows. The importer separates source revisions, resolved build inputs and
native versions, profile IDs, runner images and metrics. Missing historical
profile metadata stays missing; old results are not retroactively labeled as
desktop passes. Different revisions must not be combined into one median.

## What the probes check

Windows uses `EnumWindows`, process ownership, exact title, visible/non-minimized
state, `GetClientRect` and `ClientToScreen`, then Pillow's real desktop capture of that
client rectangle. The probe places the window inside the work area and refuses
client bounds extending beyond it (including the taskbar). Windows/Linux phases
also require an actual 960×640 physical client; geometry must stay fixed during
sampling. Capture can still contain
an occluding window; visual artifact inspection
is required. On macOS, Quartz lists on-screen windows by owner PID/title/layer/bounds;
`screencapture -l` captures the actual window including its titlebar. macOS capture
needs Screen Recording access. Missing permission, missing title/window metadata or
capture failure is recorded as failure; the probe does not assume a GUI session or
request an interactive TCC approval. A nonuniform-image check excludes the titlebar and outer borders to reject a black
client with painted chrome, but cannot prove the interface is correct. Retina scaling can change PNG
pixel dimensions relative to logical window bounds.

The driver establishes foreground state before startup captures and again before
keyboard input; it records the actual macOS frontmost PID, not just the activation
request. macOS first uses System Events, then makes bounded native
`NSRunningApplication` activation requests for the exact process. The native API's
return value is diagnostic only: the independently observed frontmost PID still
has to match. An Automation permission failure stops the check before that path.
If those requests leave another process foreground, the driver can make one
ordinary titlebar click. It re-reads the exact owned window and its bounds,
refuses an occluding window, and requires existing event-posting permission.
The click is not proof of activation: the actual foreground PID must still match.
Supplementary AppKit observations are retained to distinguish conflicting API
reports; they do not replace the acceptance gate.
macOS shortcuts use physical Quartz key transitions, including Command's
keycode/flags-changed events and release attempts in `finally`. Event-posting access
is preflighted without requesting a TCC grant or switching to a bypass route.
Denied input permission is an environment blocker, not a failed toolkit capability.
System Events appearance/foreground automation remains a separate prerequisite.

Linux uses an Xvfb display, Openbox and a dedicated D-Bus session. Window discovery
checks PID, title and `xwininfo` viewable state; ImageMagick captures the actual X11
client window. `LIBGL_ALWAYS_SOFTWARE=1` requests software OpenGL and `glxinfo -B` records
the display renderer. The session installs/selects the GTK Settings portal backend,
starts the real GNOME XSettings daemon, and supplies the same display/session
environment to D-Bus activation. It waits for the XSettings provider before running
the candidates. `xdotool`
drives the ordinary widgets and `xclip` supplies the external `CLIPBOARD` endpoint.
Native Wayland input/clipboard automation is not implemented in this driver;
an XWayland window cannot count as native Wayland coverage. The applications' own
renderer remains unknown unless reported. The isolated egui D-Bus transport test
checks protocol/restart handling only; it does not replace desktop acceptance.

The probe refreshes descendants with 200 ms delays and retains identities after reparenting.
It records family RSS and observed CPU increments once per sampling interval. Actual
cadence includes monitoring overhead. Short-lived children
between discovery polls and the final CPU interval of exiting processes may be missed.
Denied access to a tracked application process marks the scope incomplete. Cleanup
terminates only tracked application
processes and reports any survivors; the external watchdog also attempts descendant
cleanup before stopping the run. Unrelated desktop and system services are excluded.

The compositor, session bus, Settings portal, XSettings daemon, shared clipboard infrastructure and
other shared services are not allocated once per application. Their exclusion is
not a claim of zero system cost. In-process portal workers, integration threads,
private font data and caches are part of the measured app family. Installed font
sets and prior glyph use affect those caches: `system_fonts` is enabled in the
egui desktop profile, but one Unicode clipboard string does not prove every font
fallback was exercised or every language renders correctly. The clipboard probe
also does not qualify IME composition, screen readers, rich/image clipboard
formats, primary selection or persistence after application exit. Optional tray,
global-shortcut and single-instance `shell-checks` are a different workload, not
part of this baseline.

Windows `rss` is Working Set; macOS/Linux `rss` is resident memory. Summing either across
processes can double-count shared pages. Neither is the Linux PSS metric used by the
original experiment. CPU is expressed as percent of one logical core, can exceed 100%,
and is subject to OS counter resolution. The reported maximum is the largest sampled
value, not a process lifetime peak. Hosted VM scheduling and graphics differ from a
physical desktop; do not infer hardware-GPU performance or a universal toolkit ranking.

## Toolkit/runtime differences

The current fixture requests 960×640 logical client pixels in every example, fitting
the hosted desktops. Refresh receives initial keyboard focus in the persistent-widget
examples, avoiding the prior Qt filter caret workload. Windows Slint requests its
position before the first native paint; macOS Tauri explicitly sets its inner size
using Cocoa `contentLayoutRect` to account for a full-size content view whose
Tauri size includes the titlebar, and logs the applied native geometry. Recorded actual geometry and
manual screenshot inspection remain necessary; old 1120×768 runs are a separate series.

The default egui build explicitly enables the desktop feature bundle: OS clipboard,
links, system-font fallback and the event-driven Linux Settings portal bridge,
alongside the existing accessibility, bundled fonts and platform backends. An
installed dependency or an enabled feature alone does not prove the path was used.
See the [manifest](../examples/egui/Cargo.toml) and per-run feature graphs.

Egui uses Glow on Linux/macOS and reports its actual OpenGL renderer. On Windows it
uses WGPU/DX12 with the built-in FXC compiler, logging the actual adapter, backend and
device type. This is a distinct renderer variant; a software WARP adapter is not
hardware GPU evidence. Slint explicitly uses
its software renderer through winit. Qt uses Qt Widgets, with Qt 6.8.3 installed by
[install-qt-action](https://github.com/jurplel/install-qt-action) on Windows and Linux,
and Homebrew Qt on macOS. The Linux deployment requires the matching Qt GTK3
platform-theme plugin (`libqgtk3.so`) plus its GTK3/XCB runtime dependencies; its
presence and `ldd` output are recorded. The example leaves palette/style selection
to Qt and logs the observed palette, style, platform and Qt version. Installing a
plugin does not establish that it loaded or that live system appearance works.

The current GTK profile is GTK4 + libadwaita, initialized with the default
system-driven `AdwStyleManager` color scheme, not the historical bare-GTK fixture.
Linux installs `libadwaita-1-dev`, Windows installs the MSYS2 UCRT64 libadwaita
package, and macOS installs Homebrew libadwaita. Its native version is recorded
alongside GTK and the Rust binding lockfile. The extra in-process library and
private allocations belong in the memory result. Unix GTK uses the host's default
renderer unless the recorded configuration says otherwise; the Windows variant
explicitly selects Cairo and native decorations. A requested backend is not proof
of the renderer actually used. Qt/GTK/libadwaita versions may differ between OS jobs.

Tauri uses WebView2 on Windows and WKWebView on macOS, as documented in the official
[WebView reference](https://v2.tauri.app/reference/webview-versions/). The workflow records
WebView2's installed version when found in the standard machine location and the
system WebKit version on macOS. WebView2 is a runtime distinct from the installed Edge
browser; see Microsoft's [distribution guidance](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution).
Missing WebView2 is exposed by the launch diagnostic rather than treated as a pass.

WebView2 descendants are included when observable. WKWebView XPC services can sit
outside ordinary ancestry. The macOS Tauri launch uses a tiny exec-in-place wrapper
that requests separate process responsibility. The probe then verifies the app is
its own responsible process and admits WebKit helpers only when their responsible
PID matches that live app. It records PID/creation time, responsibility and resource
coalition metadata; coalition equality alone never establishes ownership. Global
responsibility discovery runs at most once per second alongside ancestry discovery.

This uses private macOS APIs, checked on the actual runner. Missing APIs, an
unverified root, missing attributable WebContent, app-process access errors, or new live unassigned
WebKit helpers refuse a complete comparison. Global helpers with a verified different
responsible PID are excluded as unrelated. Native lookup errors for unknown helpers
are retried; an unresolved live helper still refuses completion. Helpers that exit
or become zombies before attribution are retained as explicit
`vanished_unattributed_helpers` evidence, subject to the short-lived polling limit.
Access errors for already attributed app helpers remain fatal. Cleanup is never marked verified when
that external scope is incomplete. The helper and exact attribution evidence are
preserved with the candidate artifacts. Shared system services are not allocated,
and short-lived helpers can escape polling. See [the implementation and upstream
ABI sources](../tools/macos_process_scope.py). Earlier macOS runs used ancestry only
and remain explicitly incomplete in their historical report.

The Linux job attempts the selected desktop candidates and optional egui control
on its own runner. Its Ubuntu
packages, versions and initial UI state differ from the historical Debian experiment.
This workflow does not replace that experiment's leased Linux/X11 reproduction procedure
or alter its measurements. Compare like-for-like profiles within the same recorded
environment, using the independent repetitions to expose VM variation.
