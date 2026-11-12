# Desktop-integrated results — 2026-11-12

This report covers the normal **desktop-integrated** profiles, after real system
appearance changes and external text-clipboard use. The older
[2026-11-09 UI-only matrix](full-native-results.md) remains a separate historical
dataset; its memory figures and startup-only observations do not describe these
updated profiles.

**Verification status: Linux and Windows complete for the stated profile;
macOS partial, with failures retained. No hardware-iGPU or production Veranda
20/200 result is claimed.**
The six Linux/Windows jobs in
[Actions run 43251948886](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43251948886)
passed, measuring source
[`fe53a64d6759b17817d4cc1c5c995b43a8031d5c`](https://github.com/HeyVasily/rust-desktop-comparison/commit/fe53a64d6759b17817d4cc1c5c995b43a8031d5c).
Each OS has three fresh runner VMs, all five primary candidates and a separately
labeled reduced egui control. All 60 Linux/Windows light- and dark-startup
acceptance invocations passed. The failed macOS jobs from that run are diagnostic
history, not successful measurements or missing values replaced with zero.

The final selected macOS [run 43263287428](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43263287428),
source [`589a6111d79156d787471069aa9e26d5b289d5d7`](https://github.com/HeyVasily/rust-desktop-comparison/commit/589a6111d79156d787471069aa9e26d5b289d5d7),
provides one eligible visible-idle observation each for egui, Slint, Qt and Tauri.
GTK failed live-theme acceptance. Two repetitions stopped before the integrated
light-start candidates because the reduced control's process cleanup was unknown.
Both complete workflow runs therefore concluded **failure**; the successful
Linux/Windows jobs and individual eligible macOS observations are reported at
their actual scope, not promoted to an all-platform pass.

[Retained evidence and archive checksums](../measurements/desktop-integrated-2026-11-12/README.md)
make every selected result, failed invocation and selection decision reviewable.

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

### Observed runtime inventory

These are observed versions in the selected artifacts, not a promise that a
future `stable`, Homebrew, MSYS2 or hosted-image install resolves identically.

| Platform | Runner / compiler | Native toolkit and webview versions | Observed rendering details |
| --- | --- | --- | --- |
| Linux | Ubuntu 24.04 x86_64, image `20261101.360.1`; rustc/cargo **1.99.1**; four logical CPUs, approximately 16 GiB RAM | GTK **4.14.5**, libadwaita **1.5.0**, GTK3 **3.24.41**, Qt **6.8.3**, WebKitGTK **2.52.6**, Mesa **25.2.8** | egui reports **llvmpipe (LLVM 20.1.2, 256 bits)**; GTK reports `GdkX11Display` / `GskGLRenderer`; Qt reports `xcb` / Fusion and the shared GTK3 theme integration |
| Windows | Windows Server 2022 x64, image `20261101.353.1`; rustc/cargo **1.99.1**; four logical CPUs, approximately 16 GiB RAM | GTK **4.24.1**, libadwaita **1.10.0**, Qt **6.8.3**, WebView2 **131.0.2903.86** | egui reports Dx12 **Microsoft Basic Render Driver**, CPU device, driver **10.0.20348.5756**; GTK reports `GdkWin32Display` / `GskCairoRenderer`; Qt reports its Windows platform plugin / Fusion |
| macOS | macOS **15.8.2 arm64**, image `20261104.0514.1`; rustc/cargo **1.99.1**; **Apple M1 (Virtual)**, three logical CPUs, 7 GiB RAM | GTK **4.24.1**, libadwaita **1.10.0**, Qt **6.12.0** (Homebrew `qtbase 6.12.0_2`), system WebKit **20621.3.11.11.3** | egui Glow reports **Apple Software Renderer**; GTK reports `GdkMacosDisplay` / `GskGLRenderer`; Qt reports `cocoa` / `macos` style |

Slint is configured for its winit/software-renderer backend. Tauri's system
webview can use its own compositor; no unsupported claim about its GPU backend
is inferred from the other candidates' logs. Windows r1 reports a different AMD
CPU family from r2/r3 despite the same image. These are hosted-VM observations,
not controlled identical hardware or hardware-GPU laptop measurements.

The exact [Linux build evidence](../measurements/native-43251948886/r1/ubuntu-24.04/build/)
and [Windows build evidence](../measurements/native-43251948886/r1/windows-2022/build/)
include feature graphs, locks, versions and binary sizes; every repetition retains
its own files. Equal executable sizes do not mean byte-identical executable hashes.

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
The site also requires matching light/dark repetition coverage within one source
and build group. Three dark-start checks and one light-start check remain partial;
the successful light-state memory observation is still retained as **n=1**.

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

## Primary visible-idle results

Memory is MiB; brackets are the min–max of the three per-run medians. CPU is the
median observed percentage of one logical core. Each Linux/Windows candidate has
**n=3 memory observations**, plus **3 light-start and 3 dark-start acceptance
invocations**. Those six acceptance checks are not six independent memory samples.

### Linux: X11 / Adwaita / llvmpipe

Image `20261101.360.1`, run `43251948886`, source `fe53a64`, build-input digest
`afd67f4452df…`. All five desktop profiles are fully verified in this environment.

| Candidate | n | PSS, median [range] | Summed RSS, median | Idle CPU, % |
| --- | ---: | ---: | ---: | ---: |
| egui / eframe | 3 | 89.69 [89.59–93.23] | 122.68 | 0.00811 |
| GTK4 + libadwaita | 3 | 204.10 [203.82–204.15] | 245.25 | 0.00000 |
| Slint | 3 | 17.47 [17.39–17.74] | 23.41 | 0.00814 |
| Qt Widgets | 3 | 36.90 [36.83–36.90] | 54.85 | 0.00000 |
| Tauri | 3 | 336.24 [336.19–336.33] | 511.74 | 0.02333 |

GTK and egui use software OpenGL here; that cost is not a measurement of GTK's
widget tree or Rust bindings alone. Qt's complete GNOME-like integration includes
its GTK3/QtDBus dependencies. Shared session services are excluded for every app.

### Windows: native desktop / software graphics adapter

Image `20261101.353.1`, run `43251948886`, source `fe53a64`, build-input digest
`79d478c768bc…`. All five desktop profiles are fully verified in this environment.

| Candidate | n | Private working set, median [range] | Summed working set, median | Idle CPU, % |
| --- | ---: | ---: | ---: | ---: |
| egui / eframe | 3 | 31.99 [31.41–32.28] | 58.98 | 0.00000 |
| GTK4 + libadwaita | 3 | 36.09 [35.93–36.34] | 79.12 | 0.00000 |
| Slint | 3 | 10.11 [10.10–10.13] | 24.29 | 0.00000 |
| Qt Widgets | 3 | 18.36 [18.30–18.36] | 36.74 | 0.00000 |
| Tauri | 3 | 126.90 [126.70–126.93] | 283.75 | 0.17983 |

The measured Tauri family includes attributable WebView2 helpers. Zero CPU ticks
for the other candidates mean below the retained accounting resolution, not a
claim of literally no work. Tauri's per-run CPU observations span 0.165–0.234%.

### macOS

Image `20261104.0514.1`, run `43263287428`, source `589a611`, build-input digest
`1b5ccfe2dd84…`. These are **single observations from r2**, not a completed
three-repetition matrix. Every reported sample followed successful light-start,
live-theme and clipboard acceptance; the separate dark-start checks passed for
these four candidates in r1/r2/r3. Missing light-start repetitions keep their
overall series status **incomplete**.

| Candidate | Eligible n | Physical footprint, MiB | Summed RSS, MiB | Idle CPU, % | Remaining evidence |
| --- | ---: | ---: | ---: | ---: | --- |
| egui / eframe | 1 | 31.55 | 97.92 | 0.01081 | Light-start r1/r3 not run |
| GTK4 + libadwaita | 0 | — | — | — | Live-theme failure; idle refused |
| Slint | 1 | 16.60 | 97.83 | 0.00109 | Light-start r1/r3 not run |
| Qt Widgets | 1 | 28.05 | 101.30 | 0.00040 | Light-start r1/r3 not run |
| Tauri | 1 | 45.07 | 146.66 | 0.00954 | Light-start r1/r3 not run |

The reduced control in r1/r3 completed sampling, but newly observed WebKit helpers
could not be assigned to an application owner. The process gate recorded
`cleanup_status=unknown` and stopped subsequent light-start candidates. Its
`cleanup_survivors` list was empty: this is **unresolved ownership**, not evidence
that egui created WebKit processes or leaked an owned child. The reduced numbers
are excluded, and no paired delta is computed for those repetitions.

GTK's system setting and libadwaita state changed, but the dark client frame
remained dark through the eight-second light-transition deadline. Ordinary input
later caused a light redraw. This limits the tested GTK/macOS profile; it does
not establish that GTK lacks dark appearance or clipboard support.

### Linux minimized, separately measured

Same source, image and build group as the visible Linux table. The minimized state
was verified before and after each independent settling/sampling phase.

| Candidate | n | PSS, median [range] | Summed RSS, median | Idle CPU, % |
| --- | ---: | ---: | ---: | ---: |
| egui / eframe | 3 | 89.69 [89.59–93.23] | 122.68 | 0.00000 |
| GTK4 + libadwaita | 3 | 204.10 [203.81–204.15] | 245.25 | 0.00000 |
| Slint | 3 | 17.47 [17.39–17.74] | 23.41 | 0.00809 |
| Qt Widgets | 3 | 36.90 [36.83–36.90] | 54.85 | 0.00000 |
| Tauri | 3 | 329.13 [329.07–329.22] | 502.29 | 0.01557 |

Minimization did not release most retained allocations in this short observation.
Tauri's PSS median is about 7.1 MiB lower; that is an observation on this profile,
not a general lifetime-memory guarantee. Windows/macOS minimized phases were not
run and must not be inferred from visible-idle data.

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

| Environment | Paired n | Primary-memory delta, median [range], MiB |
| --- | ---: | ---: |
| Linux visible, image `20261101.360.1` | 3 | **+1.028 [+1.008–+8.201]** PSS |
| Linux minimized, same image | 3 | **+1.028 [+1.008–+8.201]** PSS |
| Windows visible, image `20261101.353.1` | 3 | **+4.926 [+4.859–+5.265]** private working set |
| macOS visible, image `20261104.0514.1` | 1 | **+1.969** physical footprint; r2 only |

These observations do **not** support an assumed very large resident-memory cost
for enabling the desktop bundle. Linux's wide pair spread also prevents treating
the +1.028 MiB median as a precise fixed overhead. The retained paired JSON uses
the recorded per-run values and rounding; it is the authoritative delta source.

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
- GTK compiled on macOS, but all three invocations were blocked by a disagreement
  in foreground verification. The probe refused keyboard input and idle sampling.
  Later diagnosis established that System Events could still report Finder while
  the native `NSWorkspace.frontmostApplication` API reported the actual GTK
  key-event recipient. This was not evidence that GTK could not become foreground.
- Windows Tauri passed in r2, but r1/r3 failed appearance checks while the webview
  had not yet rendered its first usable frame. The uniform startup budget was
  separated from the live-change deadline; blank frames still fail rather than
  qualifying as a light palette.

Run `43251948886` supplies the current Linux/Windows data and dark-startup checks
in every repetition. Its experimental in-process macOS AppKit activation path
was not retained: it did not fix the stale System Events observer and introduced
additional foreground failures. Its macOS r3 never received a runner. Those
failed/canceled jobs are not part of the current primary data.

The GTK-only [run 43260869046](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43260869046)
uses the canonical frontmost-application API from a fresh read-only JXA helper,
without importing AppKit into the long-lived Python probe. GTK then passed real
foreground ownership, both startup palettes and both external clipboard checks.
It exposed a separate stale-frame problem: the dark-to-light notification reached
libadwaita, but the client remained dark through the eight-second deadline and
became light after ordinary keyboard input. A macOS-only, event-driven redraw
invalidation was subsequently tested; no forced palette or polling was added.

The [redraw smoke run 43262165209](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43262165209)
did **not** fix GTK's stale frame. The `queue_draw()` experiment was removed before
the selected [native run 43263287428](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43263287428),
which retained the unresolved failure. The latter's
three dark-start GTK invocations and r2 light-start invocation still failed live
theme acceptance. Their original outcomes, screenshots and application logs are
retained under [the measured source's evidence directory](../measurements/native-43263287428/).
The prior run's two macOS artifacts are also retained, but explicitly excluded
from the current cohort in [archives.json](../measurements/desktop-integrated-2026-11-12/archives.json).

Previous successful samples are not relabeled as measurements of another source
revision. The earlier GTK `display()` compile ambiguity was already resolved
before run `43218424949`.

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
python3 tools/import_native_run.py 43251948886,43263287428 out/artifacts-current desktop-integrated-2026-11-12
python3 tools/build_desktop_site_data.py measurements/desktop-integrated-2026-11-12
python3 tools/build_desktop_site_data.py measurements/desktop-integrated-2026-11-12 --check
```

`out/artifacts-current` must contain the **nine selected archives** listed as
`selection: current` in [archives.json](../measurements/desktop-integrated-2026-11-12/archives.json):
six Linux/Windows directories from `43251948886` and three macOS directories from
`43263287428`, named `native-<runner>-<run-id>-r<repetition>`. The two older macOS
archives are diagnostic history, kept outside this input directory. The importer
retains build evidence, outcomes, desktop screenshots and deterministic compressed
samples under `measurements/native-<run-id>/r<repetition>/<runner>/`; series CSV/JSON
files record eligibility, exclusions, provenance groups and the paired control.
`--check` verifies that the site's published JSON matches those imported records
without rewriting it. A successful import alone is not an all-jobs-passed claim:
review `import-report.json`, all expected artifacts, acceptance and actual counts.

The [series README](../measurements/desktop-integrated-2026-11-12/README.md) links
the verified original ZIP digests, selected and diagnostic evidence, summaries,
acceptance records, paired controls and retained-file checksums. The import
contains **89 outcome records**, **62 requested/measured phase rows**, **19 primary
summary groups** and **4 diagnostic-control groups**. These are data-record counts,
not 89 successful GUI tests or 62 independent runner VMs.

The importer checked the retained samples against their summaries and captured
luminance against PNGs. Representative light/dark/restored captures were also
visually reviewed. The Python/JavaScript checks validate the evidence pipeline
and report; they do not constitute new native application runs.

## Applicability to Veranda and the hardware follow-up

At Subyard commit [`1446bdaa37e6f79e3717063b6b96643bc6b19257`](https://github.com/subyard/subyard/commit/1446bdaa37e6f79e3717063b6b96643bc6b19257),
the [GTK product and its acceptance harness](https://github.com/subyard/subyard/blob/1446bdaa37e6f79e3717063b6b96643bc6b19257/veranda/desktop/README.md)
already use the shared Rust client, a real Go owner and **20 configured yards / 200
actual project records**. This does not mean all 200 project widgets are rendered
simultaneously or all acceptance gates have passed. The examples measured here
use **10 synthetic yards / 100 projects without RPC**, and the GTK example adds
libadwaita. These profiles are not measurements of replacing Veranda's GTK shell.

The primary missing experiment is the matched GTK/egui product slice on a user
desktop with a **verified hardware GPU, including integrated graphics**. None of
the three selected hosted environments supplies that evidence: egui reports
llvmpipe, Microsoft Basic Render Driver or Apple Software Renderer. Their memory
values must not be used to predict hardware-rendered RAM, interaction latency or
battery use. Software CI remains a separate compatibility and regression case.

The smallest product-specific extension is a read-only egui fleet view using
Veranda's existing Rust client/store and unchanged RPC contract, with the same
real 20/200 inventory and comparable GTK view. Preserve snapshot/events,
reconnect/cancellation, SSH trust and process ownership; introduce no polling or
new authority. Test actual input, clipboard, accessibility and HiDPI before
resource acceptance, then compare visible/minimized idle, startup, burst events,
sleep/reconnect and 100 connection cycles. A GPU adapter must be recorded by the
application; the presence of a display server or a GPU in the physical host is
insufficient evidence of the renderer used by a guest process.

The existing GTK software-resource prerequisite is documented as:

```sh
python3 dev/e2e/veranda-wayland-resources.py /absolute/candidate.deb /absolute/yard --gtk --x11 --short
```

After its review, omitting `--short` runs the existing 30-start and visible/minimized
idle sequence. For the separate native Wayland fixture omit `--x11` and use a fresh
VM. These are [existing GTK harness commands](https://github.com/subyard/subyard/blob/1446bdaa37e6f79e3717063b6b96643bc6b19257/dev/e2e/veranda-wayland-resources.py),
**not an egui driver or hardware-GPU measurement**. Adapting readiness/input to
egui and running on actual iGPU hardware remain outstanding. This report proposes
no production UI migration and claims no completed hardware result.

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
