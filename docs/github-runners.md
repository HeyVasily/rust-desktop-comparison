# Native desktop diagnostics on GitHub-hosted runners

The manually dispatched [workflow](../.github/workflows/native-comparison.yml) builds
release examples and attempts actual GUI launches on Windows, macOS and Linux.
Its defaults request all three OS jobs and full memory/CPU sampling.
The `platforms` input supports `native` (Windows and macOS), individual `windows`,
`macos` or `linux` (`ubuntu-24.04`), and `all`.
Each OS job runs its candidates sequentially on the same machine, with at most two
jobs running concurrently. A successful build alone does not establish GUI access.
The workflow is an experiment, not evidence that either runner supports every app.

As of 2026-11-07, GitHub lists Windows Server 2022 x64 and macOS 15 ARM64 as available
standard images. macOS 14 has retired from Actions. Image contents change, so artifacts
record the image version, OS, architecture, CPU, memory, Rust compiler and native
library versions. See the official [runner image inventory](https://github.com/actions/runner-images#available-images).
Different operating systems and architectures must be analyzed separately.
The probe uses the captured Python 3.12 executable throughout the job, including
child processes; tool installers can otherwise change which `python` is on `PATH`.

## Run and inspect

In the repository's Actions tab, select **Native desktop comparison**, then **Run
workflow**. Set `comparison` to false for a shorter setup diagnostic; leave it enabled
for the full footprint matrix. The diagnostic
waits up to 45 seconds for an owned window with the expected title, settles for five
seconds, waits up to 45 additional seconds for a nonblank client capture, captures it, collects ten sampling intervals, and captures it again. Each candidate
has a 480-second watchdog; the job has a 90-minute limit, including compilation.

Inspect downloaded `native-<runner>-<run-id>` artifacts before interpreting results:

- `build/`: compilation logs, compiler/native library versions, and the exact generated
  Cargo lockfiles when a new example did not yet have a committed lockfile. Subsequent
  builds should commit those locks; the workflow builds with `--locked` after resolution.
  Rust sources are formatted on the runner and copied under
  `build/formatted/` for review. The Windows renderer dependency resolution is now
  committed; subsequent builds use the preserved lock with `--locked`.
- `<candidate>/outcome.json`: actual outcome, window owner/title/bounds, capture dimensions,
  environment, process scope, limitations, summary and cleanup status.
- `<candidate>/application.log`: stdout/stderr, including an observed renderer when the
  application reports one. A configured renderer is not proof of the renderer in use.
- `<candidate>/diagnostic*.png`: real OS captures. Inspect for the intended interface,
  clipping, blank content, occlusion and correct initial fixture state. These captures
  show each example's initial UI state; they do not reproduce the historical Linux snapshot-1 interaction.
  In particular, the original controls and new examples differ in initial selection.
- `<candidate>/*-samples.json`: raw timestamps, process identities, CPU counters and RSS.
  Samples are written incrementally so a later failure retains earlier observations.

Enable `comparison` for 30 seconds of settling followed by 120 sampling intervals.
Each interval includes one second of delays plus process-monitoring overhead; actual
elapsed time is retained and used for CPU normalization. This phase runs only after that candidate's diagnostic and scope checks
pass. Windows/macOS measure visible idle state only. Linux additionally minimizes the
window, verifies both `_NET_WM_STATE_HIDDEN` and `IsUnMapped`, and repeats the settling
and 120-interval phase with the minimized state verified again afterward. No interaction or peak-memory
claim is made. A failed candidate remains a failed job after artifacts upload. All
five candidates are configured on each OS, including GTK4 through MSYS2 UCRT64 on
Windows. Other configured examples are attempted even if an earlier build
or diagnostic fails, provided cleanup is explicitly clean or no process was launched.
Missing/unknown cleanup status, survivors or denied process access stop subsequent
candidates. An overall watchdog expiry also stops subsequent candidates to avoid
contaminating their measurements.

## What is actually validated

Windows uses `EnumWindows`, process ownership, exact title, visible/non-minimized
state, `GetClientRect` and `ClientToScreen`, then Pillow's real desktop capture of that
client rectangle. The probe places the window inside the work area and refuses
client bounds extending beyond it (including the taskbar). Capture can still contain
an occluding window; visual artifact inspection
is required. On macOS, Quartz lists on-screen windows by owner PID/title/layer/bounds;
`screencapture -l` captures the actual window including its titlebar. macOS capture
needs Screen Recording access. Missing permission, missing title/window metadata or
capture failure is recorded as failure; the probe does not assume a GUI session or
request an interactive TCC approval. A nonuniform-image check excludes the titlebar and outer borders to reject a black
client with painted chrome, but cannot prove the interface is correct. Retina scaling can change PNG
pixel dimensions relative to logical window bounds.

Linux uses an Xvfb display, Openbox and a dedicated D-Bus session. Window discovery
checks PID, title and `xwininfo` viewable state; ImageMagick captures the actual X11
client window. `LIBGL_ALWAYS_SOFTWARE=1` requests software OpenGL and `glxinfo -B` records
the display renderer. The applications' own renderer remains unknown unless reported.

The probe refreshes descendants with 200 ms delays and retains identities after reparenting.
It records family RSS and observed CPU increments once per sampling interval. Actual
cadence includes monitoring overhead. Short-lived children
between discovery polls and the final CPU interval of exiting processes may be missed.
Denied access marks the scope incomplete. Cleanup terminates only tracked application
processes and reports any survivors; the external watchdog also attempts descendant
cleanup before stopping the run. Unrelated desktop and system services are excluded.

Windows `rss` is Working Set; macOS/Linux `rss` is resident memory. Summing either across
processes can double-count shared pages. Neither is the Linux PSS metric used by the
original experiment. CPU is expressed as percent of one logical core, can exceed 100%,
and is subject to OS counter resolution. The reported maximum is the largest sampled
value, not a process lifetime peak. Hosted VM scheduling and graphics differ from a
physical desktop; do not infer hardware-GPU performance or a universal toolkit ranking.

## Toolkit/runtime differences

The current fixture requests 960×640 logical client pixels in every example, fitting
the hosted desktops. Refresh receives initial keyboard focus in the persistent-widget
examples, avoiding the prior Qt filter caret workload. Recorded actual geometry and
manual screenshot inspection remain necessary; old 1120×768 runs are a separate series.

Egui uses Glow on Linux/macOS and reports its actual OpenGL renderer. On Windows it
uses WGPU/DX12 with the built-in FXC compiler, logging the actual adapter, backend and
device type. This is a distinct renderer variant; a software WARP adapter is not
hardware GPU evidence. Slint explicitly uses
its software renderer through winit. Qt uses Qt Widgets, with Qt 6.8.3 installed by
[install-qt-action](https://github.com/jurplel/install-qt-action) on Windows and Homebrew
Qt on macOS. GTK4 uses the host's default renderer; the workflow does not claim to
have observed its renderer type. Qt/GTK library versions may differ between OS jobs.

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
unverified root, missing attributable WebContent, access errors, or new unassigned
WebKit helpers refuse a complete comparison. Cleanup is never marked verified when
that external scope is incomplete. The helper and exact attribution evidence are
preserved with the candidate artifacts. Shared system services are not allocated,
and short-lived helpers can escape polling. See [the implementation and upstream
ABI sources](../tools/macos_process_scope.py). Earlier macOS runs used ancestry only
and remain explicitly incomplete in their historical report.

The optional Linux job measures all five candidates on its own runner. Its Ubuntu
packages, versions and initial UI state differ from the historical Debian experiment.
This workflow does not replace that experiment's leased Linux/X11 reproduction procedure
or alter its measurements; only compare candidates within a single new job.
