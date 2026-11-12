# Desktop-integrated results — 2026-11-12

This report covers the normal **desktop-integrated** profiles, after real system
appearance changes and external text-clipboard use. The older
[2026-11-09 UI-only matrix](full-native-results.md) remains a separate historical
dataset; its memory figures and startup-only observations do not describe these
updated profiles.

**Verification status: pending final artifact review.** The current full rerun is
[Actions run 43251948886](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43251948886),
measuring source
[`fe53a64d6759b17817d4cc1c5c995b43a8031d5c`](https://github.com/HeyVasily/rust-desktop-comparison/commit/fe53a64d6759b17817d4cc1c5c995b43a8031d5c).
It requests three fresh runner VMs per operating system, all five primary
candidates, a separate reduced egui control, and light- and dark-startup
acceptance in every repetition. These are the **requested checks**, not a claim
that every job passed or that each provenance group contains three samples.

<!-- FINALIZE_STATUS: Replace the pending status only after reviewing all nine
artifacts, import exclusions, provenance groups, screenshots and final CI gates.
Keep the measurement source above distinct from later report-only revisions. -->

## What was built

| Candidate | Pinned application dependencies / configured profile | Runtime details that must accompany the result |
| --- | --- | --- |
| egui / eframe | eframe **0.37.0**; default `desktop` feature enables OS clipboard, browser links, system-font fallback and the Linux Settings portal observer; existing AccessKit, bundled fonts and renderers remain enabled | Glow on Linux/macOS and WGPU on Windows; retain the actual backend/renderer from application logs rather than infer it from enabled features |
| GTK4 + libadwaita | gtk4-rs **0.11.5**, Rust libadwaita bindings **0.9.2**; initializes libadwaita's system-following StyleManager | Native GTK and libadwaita versions are separate from their Rust binding versions; Windows uses MSYS2 UCRT64 and native window decorations |
| Slint | Slint and slint-build **1.18.1**; winit backend, software renderer and accessibility enabled | Record the backend selected by the actual application and its platform environment |
| Qt Widgets | C++17; Qt **6.8.3** kits on Linux and Windows; Homebrew Qt on macOS | Linux uses the matching Qt GTK3 platform-theme plugin; Windows uses Fusion with the native platform palette; macOS retains its native style |
| Tauri | Tauri **2.12.5**, tauri-build **2.7.4**; embedded static HTML/CSS/JS and normal editable controls | WebKitGTK on Linux, WebView2 on Windows, system WKWebView on macOS; their attributable helper processes are included |

Cargo lockfiles are committed and builds use `--locked`. Rust's `stable` channel,
Homebrew/MSYS2 packages and hosted runner contents are not immutable version
pins; their **observed versions and image identity** belong to each artifact.
The [workflow](../.github/workflows/native-comparison.yml) records those versions,
resolved target-specific feature graphs, source-file checksums, executable hashes
and sizes. The native libadwaita runtime, Linux Qt's GTK3/QtDBus mappings, and egui's
in-process integration resources are included in their application footprints.

<!-- FINALIZE_VERSIONS: Fill observed compiler, native GTK/libadwaita, Qt macOS,
webview, renderer, architecture and runner-image versions from THIS run's build
files and outcomes. Do not reuse versions from the previous failed run. -->

**Observed runtime/version inventory: pending.**

## Acceptance and sampling

All examples show the same synthetic ten-yard, 100-project fixture with an
editable filter, selection, scrolling and an in-memory Refresh counter. There
is no backend, filesystem inventory or periodic data-refresh workload. The
intended window is 960×640 logical pixels; Linux/Windows additionally validate
physical client dimensions. macOS uses Quartz outer-window captures, including
the titlebar, and is not presented as identical client-only geometry.

Before an integrated idle measurement, the probe must:

1. Set and independently read the real OS light preference, then capture a
   nonblank application window with the corresponding palette.
2. Observe light → dark → light in the **same live process and window**, retaining
   screenshots and process identity. No application-specific forced palette or
   relaunch substitutes for system-driven changes.
3. Paste synthetic Unicode text from an externally seeded OS clipboard into the
   ordinary filter; replace that clipboard with a different sentinel; copy the
   filter back and verify the external text exactly. An ignored copy cannot pass
   by returning the original clipboard seed.
4. Clear the filter, remove editor focus, park the pointer, restore the fixture
   and initial palette, and stop probe-owned clipboard helpers before sampling.

A separate dark-startup invocation performs dark → light → dark plus the same
clipboard test in **every repetition**. It supplies acceptance evidence, not an
extra ranked memory sample. A light-state sample does not disappear merely
because another invocation fails, but the overall desktop profile must not be
marked fully verified when its required dark-startup evidence failed or is missing.

Startup permits up to 30 seconds for a correctly themed nonblank first frame
after the owned window is found; live transitions retain an eight-second budget.
The same budgets apply to every candidate. macOS input requires independently
verified foreground ownership before keyboard events are sent. Captures,
readiness attempts, actual elapsed time and restoration outcomes remain evidence,
not just a top-level success label.

After a short diagnostic, the full phase uses **30 seconds of settling and 120
sampling intervals**, retaining a baseline plus 120 samples. Each interval has
one second of delays plus monitoring overhead; actual elapsed time is recorded
and used for CPU normalization. Candidates run sequentially on each runner.
Linux additionally repeats settling and sampling with the minimized state
verified before and after the phase. Windows/macOS have visible-idle measurements
only. A failed acceptance, incomplete process scope or unsafe cleanup prevents
an invocation from entering the primary summary.

The importer recomputes resource statistics from retained samples, checks
monotonic timestamps and CPU counters, verifies process-family sums and accepted
application identity, and compares them with the reported summaries. Missing or
inconsistent samples are rejected rather than turned into small memory values.

## How to read the results

| Platform | Primary memory metric | Additional reported metric |
| --- | --- | --- |
| Linux | Application-family PSS | Summed RSS |
| Windows | Application-family private working set | Summed Working Set |
| macOS | Application-family physical footprint | Summed RSS |

The primary metrics are **not interchangeable across operating systems**.
Compare candidates within one OS, runner image and rendering environment.
Summed RSS/Working Set can double-count shared pages. Webview helpers are part of
Tauri's application family; macOS also verifies WKWebView responsibility ownership
because ancestry alone can miss helpers managed by the OS.

Each repetition first produces its median across the 120 post-baseline samples.
An aggregate reports the median and min–max range of those repetition medians,
with the actual accepted **n**, failures and outlier flags retained. The range is
not a confidence interval. Aggregation does not combine different workflow runs,
source revisions, source/build hashes, profiles, memory metrics or runner images.
A requested three-repetition matrix can therefore legitimately yield separate
n=1 and n=2 groups during a hosted image rollout.

CPU is observed process user+system time as a percentage of **one logical core**.
Zero recorded ticks means below accounting resolution over that interval, not
literally no work. Tiny idle differences are not a useful performance ranking.
Executable bytes are reported separately: they exclude required shared runtimes
and do not predict warmed resident-memory cost.

<!-- FINALIZE_PRIMARY_RESULTS: Insert the imported per-platform AND per-image
tables here. For each candidate show acceptance, measured n, primary median and
range, summed RSS/WS, and idle CPU. Keep failed/missing candidates explicit;
never insert zero for a missing measurement. If images split, show both groups.
Link the imported series summary.csv, runs.csv and desktop-acceptance.csv. -->

**Primary visible-idle results: pending verified artifact import.**

<!-- FINALIZE_MINIMIZED: Insert the separate Linux minimized results from the
same imported source/image groups. Do not mix them into visible-idle medians. -->

**Linux minimized results: pending verified artifact import.**

## Paired egui integration cost

The separately named `egui_reduced` executable is built from the same source and
lockfile with `--no-default-features`; it retains the chosen renderer, display
backends, bundled fonts and accessibility but omits the normal desktop bundle.
It is a **diagnostic control**, never a primary desktop candidate.

The runner places the control before integrated egui in odd repetitions and
after it in even repetitions. A pair must share its runner/repetition, source,
build inputs, display session, renderer, fonts, final light palette, fixture
state and sampling policy. The control's light OS preference is independently
checked before and after its measurement, but that does not qualify it for
external clipboard or live-theme acceptance.

The reported delta is **integrated minus reduced**, paired within one runner
before aggregating across compatible repetitions. The integrated build is
measured after real clipboard/theme use; the reduced build cannot exercise that
workload. Thus the delta describes the **whole configured profile after use**,
including retained caches and allocations, not clipboard-only or theme-only
memory. It is not derived by subtracting unrelated historical medians.

Negative or inconsistent small deltas remain visible. Neither added dependency
count nor executable growth proves a large resident-memory increase. Three
sequential pairs do not establish statistical significance or a general result
for other machines, renderers or desktop environments.

<!-- FINALIZE_PAIRED_AB: Insert each eligible OS/image group's pair count,
primary-memory median delta and min/max individual deltas from paired-egui-ab.json.
Include a restrained interpretation based on the actual values, not an assumed
increase. Link the raw paired report and keep controls outside primary tables. -->

**Paired integrated/reduced observations: pending verified artifact import.**

## Verification history

The preceding [run 43218424949](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43218424949),
source [`76bc29b`](https://github.com/HeyVasily/rust-desktop-comparison/commit/76bc29baa329bbc0843b2d294a45f7df04c824e3),
is a diagnostic attempt, **not the current complete baseline**:

The [five failed cases are retained in the repository](../measurements/desktop-validation-2026-11-12/README.md),
including original outcomes, available captures and verified archive checksums;
their review does not depend on the temporary Actions artifact retention period.

- All three Linux jobs passed, but r1 used image `20261111.370.1` while r2/r3 used
  `20261101.360.1`. The importer correctly kept n=1 and n=2 groups separate. At
  that revision only r1 had a separate dark-startup case; the older-image group
  could not borrow that acceptance result.
- GTK compiled on macOS, but all three invocations were blocked at foreground
  verification: the System Events request did not make the standalone GTK
  process frontmost. The probe refused to send keyboard input or publish its
  idle footprint. Native AppKit activation by exact PID was added while keeping
  the independent foreground check and respecting Automation permission denials.
- Windows Tauri passed in r2, but r1/r3 failed appearance checks while the webview
  had not yet rendered its first usable frame. The uniform startup budget was
  separated from the live-change deadline; blank frames still fail rather than
  qualifying as a light palette.

The current rerun includes those probe corrections and dark-startup checks in
every repetition. It must supply its own outcomes; previous successful samples
are not relabeled as measurements of the new source revision. The earlier GTK
`display()` compile ambiguity was already resolved before run 43218424949.

## Evidence and reproduction

Use the [runner procedure](github-runners.md) and
[full measurement contract](methodology.md) for setup. The acceptance driver
changes global appearance and replaces the OS clipboard with synthetic text;
run it only in **disposable test desktops**, not an active personal session.
Original appearance is restored, but private clipboard formats and ownership
are not backed up or restored.

After downloading and verifying all selected artifact archives, an import is
reproducible with:

```sh
python3 tools/import_native_run.py 43251948886 out/artifacts-current desktop-integrated-2026-11-12
python3 tools/build_desktop_site_data.py measurements/desktop-integrated-2026-11-12
python3 tools/build_desktop_site_data.py measurements/desktop-integrated-2026-11-12 --check
```

`out/artifacts-current` must contain extracted directories named
`native-<runner>-43251948886-r<repetition>`. The importer retains build evidence,
outcomes, desktop screenshots and deterministic compressed samples under
`measurements/native-43251948886/r<repetition>/<runner>/`; series CSV/JSON files
record eligibility, exclusions, provenance groups and the paired control.
`--check` verifies that the site's published JSON matches those imported records
without rewriting it. A successful import alone is not an all-jobs-passed claim:
review `import-report.json`, all expected artifacts, acceptance and actual counts.

<!-- FINALIZE_EVIDENCE: Link the retained evidence directories, series README,
summary/acceptance/paired data and useful light/dark/clipboard screenshots once
they exist in the repository. Record final verification counts, not planned ones. -->

## Limits of this baseline

- Linux is the named **GNOME-like X11/Adwaita** profile on Xvfb with Mesa
  llvmpipe, not native Wayland or a hardware-GPU benchmark. Its real Settings
  portal and XSettings daemon expose both color preference and shared GTK3
  theme; both are changed and independently verified for every candidate.
  This does not claim all Linux desktops use the same integration route.
- Shared desktop services, the compositor/X server, session bus, probe and
  clipboard-test helpers are outside the measured application family. Their
  required presence is not a zero-system-cost claim. GPU/VRAM allocations are
  not comprehensively attributed.
- The memory observations are post-exercise idle state, not lifetime peak,
  startup latency, scrolling throughput, interactive frame rate or battery use.
  Cloud VM timing and software rendering are not substitutes for a laptop test.
- The Unicode text-clipboard round trip does not qualify image/HTML/MIME
  transfers, clipboard persistence after exit, primary selection, every Wayland
  compositor, full font coverage or IME/dead-key behavior.
- AccessKit/accessibility features being enabled is not end-to-end screen-reader
  qualification. Native menus, dialogs, notifications, autostart, associations,
  credential stores, mixed-DPI moves and installed-bundle behavior need dedicated
  acceptance tests.
- Tray, global shortcuts and single-instance checks remain an
  [optional shell profile](shell-integration.md), not part of this memory ranking.
  Real application backends and production data must be measured separately.

See the [profile specification](desktop-integration.md) for the distinction
between a framework capability, enabled integration, observed behavior and
measured cost. A failed environment-specific check does not establish that an
entire toolkit lacks dark mode or clipboard support.
