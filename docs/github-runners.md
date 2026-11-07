# Native desktop diagnostics on GitHub-hosted runners

The manually dispatched [workflow](../.github/workflows/native-comparison.yml) builds
release examples and attempts actual GUI launches on `windows-2022` and `macos-15`.
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
workflow**. Leave `comparison` disabled for the first run. The default diagnostic
waits up to 45 seconds for an owned window with the expected title, settles for five
seconds, captures it, collects ten sampling intervals, and captures it again. Each candidate
has a 480-second watchdog; the job has a 90-minute limit, including compilation.

Inspect downloaded `native-<runner>-<run-id>` artifacts before interpreting results:

- `build/`: compilation logs, compiler/native library versions, and the exact generated
  Cargo lockfiles when a new example did not yet have a committed lockfile. Subsequent
  builds should commit those locks; the workflow builds with `--locked` after resolution.
  New Slint/Tauri Rust sources are formatted on the runner and copied under
  `build/formatted/` for review; the original measured egui source is not formatted.
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
claim is made. A failed candidate remains a failed job after artifacts upload. Windows
GTK is explicitly `not_run`, because this workflow does not configure its MSYS2 GTK4
compiler/runtime. Other configured examples are attempted even if an earlier build
or diagnostic fails, provided cleanup is explicitly clean or no process was launched.
Missing/unknown cleanup status, survivors or denied process access stop subsequent
candidates. An overall watchdog expiry also stops subsequent candidates to avoid
contaminating their measurements.

## What is actually validated

Windows uses `EnumWindows`, process ownership, exact title, visible/non-minimized
state, `GetClientRect` and `ClientToScreen`, then Pillow's real desktop capture of that
client rectangle. Capture can contain an occluding window; visual artifact inspection
is required. On macOS, Quartz lists on-screen windows by owner PID/title/layer/bounds;
`screencapture -l` captures the actual window including its titlebar. macOS capture
needs Screen Recording access. Missing permission, missing title/window metadata or
capture failure is recorded as failure; the probe does not assume a GUI session or
request an interactive TCC approval. A nonuniform-image check rejects obvious blank
captures but cannot prove the interface is correct. Retina scaling can change PNG
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

Egui requests Glow and reports the actual OpenGL renderer in its log. A Windows
runner without a sufficient OpenGL context may fail at launch. Slint explicitly uses
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

WebView2 descendants are included when observable. WKWebView can use XPC helpers
outside the app's process ancestry. The probe records newly appearing unassigned
WebKit helpers, but cannot reliably allocate existing/shared helpers to this app.
**macOS Tauri is therefore always marked `incomplete_process_scope` after a successful
GUI diagnostic, and its full comparison phase is refused.** Its screenshot and partial
process samples remain useful evidence of GUI availability, not a total application
memory measurement. This bounded probe does not attempt a general XPC attribution
system or claim that invisible child costs are zero.

The optional Linux job measures all five candidates on its own runner. Its Ubuntu
packages, versions and initial UI state differ from the historical Debian experiment.
This workflow does not replace that experiment's leased Linux/X11 reproduction procedure
or alter its measurements; only compare candidates within a single new job.
