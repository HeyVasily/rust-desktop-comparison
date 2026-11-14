# Desktop-integrated results — 2026-11-14

This report covers the normal **desktop-integrated** profiles, after real system
appearance changes and external text-clipboard use. The older
[2026-11-09 UI-only matrix](full-native-results.md) remains a separate historical
dataset; its memory figures and startup-only observations do not describe these
updated profiles.

**Verification status: 14 of 15 platform/candidate profiles fully verified.
GTK4 + libadwaita on macOS failed live-theme acceptance in all six invocations.
No hardware-iGPU or production Veranda 20/200 result is claimed.**

| Platform | Run | Measured source | Jobs | Result |
| --- | --- | --- | --- | --- |
| Linux | [43579539989](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43579539989) | [`52b840e`](https://github.com/HeyVasily/rust-desktop-comparison/commit/52b840ef822f4af41d713b5541fb49ba2cab5923) | 3 of 3 passed | All five profiles fully verified; repetitions split across two runner images (n=1 + n=2) |
| Windows | [43580078566](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43580078566) | [`d1b3951`](https://github.com/HeyVasily/rust-desktop-comparison/commit/d1b3951dde8d17761509f8d5b383fa1c153a9a43) | 3 of 3 passed | All five profiles fully verified, n=3 |
| macOS | [43579539989](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43579539989) | `52b840e` | 0 of 3 passed | egui, Slint, Qt, Tauri fully verified, n=3; GTK failed |

Each OS has three fresh runner VMs, all five primary candidates and a separately
labeled reduced egui control. The macOS jobs fail only on the strict gate that
requires every configured candidate to pass; the four passing candidates are
reported at their actual scope, GTK's failure is retained, not replaced by zero.

[Retained evidence and archive checksums](../measurements/desktop-integrated-2026-11-14/README.md)
make every selected result, failed invocation and selection decision reviewable.
The earlier 2026-11-12 import (runs 43251948886 and 43263287428: Linux/Windows
complete, macOS n=1) is preserved at tag
[`evidence/desktop-import-2026-11-12`](https://github.com/HeyVasily/rust-desktop-comparison/tree/evidence/desktop-import-2026-11-12/measurements).

## What was built

| Candidate | Pinned application dependencies / configured profile | Runtime details that must accompany the result |
| --- | --- | --- |
| egui / eframe | eframe **0.37.0**; default `desktop` feature enables OS clipboard, browser links, system-font fallback and the Linux Settings portal observer; existing AccessKit, bundled fonts and renderers remain enabled | Glow on Linux/macOS and WGPU on Windows; retain the actual backend/renderer from application logs rather than infer it from enabled features |
| GTK4 + libadwaita | gtk4-rs **0.11.5**, Rust libadwaita bindings **0.9.2**; initializes libadwaita's system-following StyleManager | Native GTK and libadwaita versions are separate from their Rust binding versions; Windows uses MSYS2 UCRT64 and native window decorations |
| Slint | Slint and slint-build **1.18.1**; winit backend, software renderer and accessibility enabled | Record the backend selected by the actual application and its platform environment |
| Qt Widgets | C++17; Qt **6.8.3** kits on Linux and Windows; Homebrew Qt on macOS | Linux uses the matching Qt GTK3 platform-theme plugin; Windows uses Fusion with the native platform palette; macOS retains its native style |
| Tauri | Tauri **2.12.5**, tauri-build **2.7.4**; embedded static HTML/CSS/JS and normal editable controls | WebKitGTK on Linux, WebView2 on Windows, system WKWebView on macOS; their attributable helper processes are included |

**Source drift.** Windows was re-run at `d1b3951` because its first jobs in
43579539989 stopped in the regression-test step (POSIX-only site smoke tests)
before building anything. `d1b3951` differs from `52b840e` only in
`tools/import_native_run.py` and tests; examples, probes and the workflow are
identical, and the importer does not run on the runners.

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
| Linux | Ubuntu 24.04 x86_64, images `20261111.127.1` (r1) and `20261111.370.1` (r2/r3); rustc/cargo **1.100.0**; four logical CPUs, approximately 16 GiB RAM | GTK **4.14.5**, libadwaita **1.5.0**, GTK3 **3.24.41**, Qt **6.8.3**, WebKitGTK **2.52.6**, Mesa **25.2.8** | egui reports **llvmpipe (LLVM 20.1.2, 256 bits)**; GTK reports `GdkX11Display` / `GskGLRenderer`; Qt reports `xcb` / Fusion and the shared GTK3 theme integration |
| Windows | Windows Server 2022 x64, image `20261112.366.7`; rustc/cargo **1.100.0**; four logical CPUs, approximately 16 GiB RAM | GTK **4.24.1**, libadwaita **1.10.0**, Qt **6.8.3**, WebView2 **131.0.2903.86** | egui reports Dx12 **Microsoft Basic Render Driver**, CPU device, driver **10.0.20348.5756**; GTK reports `GdkWin32Display` / `GskCairoRenderer`; Qt reports its Windows platform plugin / Fusion |
| macOS | macOS **15.8.2 arm64**, image `20261104.0514.1`; rustc/cargo **1.100.0**; **Apple M1 (Virtual)**, three logical CPUs, 7 GiB RAM | GTK **4.24.1**, libadwaita **1.10.0**, Qt **6.12.0** (Homebrew `qtbase 6.12.0_2`), system WebKit **20621.3.11.11.3** | egui Glow reports **Apple Software Renderer**; GTK reports `GdkMacosDisplay` / `GskGLRenderer`; Qt reports `cocoa` / `macos` style |

Slint is configured for its winit/software-renderer backend. Tauri's system
webview can use its own compositor; no unsupported claim about its GPU backend
is inferred from the other candidates' logs. The three Windows VMs reported
three different CPU models (two AMD models, one Intel) on the same image.
These are hosted-VM observations, not controlled identical hardware or
hardware-GPU laptop measurements.

The exact [Linux build evidence](../measurements/native-43579539989/r1/ubuntu-24.04/build/),
[Windows build evidence](../measurements/native-43580078566/r1/windows-2022/build/)
and [macOS build evidence](../measurements/native-43579539989/r1/macos-15/build/)
include versions, build logs and binary sizes; every repetition retains its own
files. Resolved feature graphs are not copied; `build/inputs-sha256.json` keeps
their digests. Equal executable sizes do not mean byte-identical executable hashes.

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
and build group. A selected candidate without a probe outcome is imported as a
failed repetition: `not_run` when a stopped sequence never started it, `failed`
with unknown cleanup when the runner's watchdog or launcher stopped it. Without
any probe outcome on the VM it keeps the artifact's run, repetition and source,
with its measurement mode recorded as unknown, so it cannot silently shrink n.

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
because ancestry alone can miss helpers managed by the OS. A WebKit helper that
appears while a non-webview candidate runs is recorded as foreign
(`foreign_new_web_helpers`) and does not block it; none appeared in this run.

Each repetition first produces its median across the 120 post-baseline samples.
An aggregate reports the median and min–max range of those repetition medians,
with the actual accepted **n**, failures and outlier flags retained. The range is
not a confidence interval. Aggregation does not combine different workflow runs,
source revisions, source/build hashes, profiles, memory metrics or runner images.

CPU is observed process user+system time as a percentage of **one logical core**.
Zero recorded ticks means below accounting resolution over that interval, not
literally no work. Tiny idle differences are not a useful performance ranking.
Executable bytes are reported separately: they exclude required shared runtimes
and do not predict warmed resident-memory cost.

## Primary visible-idle results

Memory is MiB; brackets are the min–max of the per-run medians. CPU is the
median observed percentage of one logical core. Each memory observation follows
its own light-start acceptance; each repetition also has a dark-start acceptance
invocation, which is not an extra memory sample.

### Linux: X11 / Adwaita / llvmpipe

Run `43579539989`, source `52b840e`, build-input digest `73353e74650a…`. The
hosted image rollout placed r1 on `20261111.127.1` and r2/r3 on `20261111.370.1`,
so each candidate has two provenance groups. Both groups are fully verified.
A Linux-only rerun ([43583529539](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43583529539))
was meant to put all three repetitions on one image; it split as well (r1/r2
`…370.1`, r3 `…127.1`), so this run was kept and runs are never pooled. That
rerun disagrees with this run for Qt; see below.

| Candidate | PSS, r2/r3 `…370.1` (n=2) median [range] | PSS, r1 `…127.1` (n=1) | Summed RSS, r2/r3 median | Idle CPU, r2/r3 % |
| --- | ---: | ---: | ---: | ---: |
| egui / eframe | 91.64 [89.82–93.46] | 89.78 | 124.76 | 0.00406 |
| GTK4 + libadwaita | 203.91 [203.89–203.92] | 204.45 | 245.00 | 0.00000 |
| Slint | 17.61 [17.34–17.88] | 17.16 | 23.54 | 0.00407 |
| Qt Widgets | 42.58 [42.56–42.59] | 42.55 | 60.72 | 0.00000 |
| Tauri | 336.03 [335.72–336.33] | 335.45 | 511.66 | 0.02353 |

GTK and egui use software OpenGL here; that cost is not a measurement of GTK's
widget tree or Rust bindings alone. Qt's complete GNOME-like integration includes
its GTK3/QtDBus dependencies. Shared session services are excluded for every app.
**Qt's Linux figure is run-dependent, not image-dependent.** The not-selected
rerun 43583529539 used the same two images, the same Qt executable
(`beed48d9018f…`) and the same package versions, and measured Qt PSS of
36.75 / 37.20 / 36.84 MiB (r1/r2 `…370.1`, r3 `…127.1`), close to the 36.90 of
the 2026-11-12 run. All three repetitions of this run sit at 42.55–42.59 MiB.
The other four candidates agree between the two runs within 2 MiB. Treat Linux
Qt as about 37–43 MiB PSS; the cause of the 5.7 MiB run-level shift is not
isolated.

### Windows: native desktop / software graphics adapter

Run `43580078566`, image `20261112.366.7`, source `d1b3951`, build-input digest
`29a2d2339dbb…`. All five desktop profiles are fully verified, n=3.

| Candidate | n | Private working set, median [range] | Summed working set, median | Idle CPU, % |
| --- | ---: | ---: | ---: | ---: |
| egui / eframe | 3 | 31.68 [31.32–34.35] | 58.73 | 0.00000 |
| GTK4 + libadwaita | 3 | 36.25 [36.13–36.27] | 79.24 | 0.00000 |
| Slint | 3 | 10.07 [10.05–10.20] | 24.30 | 0.00000 |
| Qt Widgets | 3 | 18.38 [18.27–18.45] | 36.85 | 0.00000 |
| Tauri | 3 | 125.72 [125.39–126.41] | 281.69 | 0.10708 |

The measured Tauri family includes attributable WebView2 helpers. Zero CPU ticks
for the other candidates mean below the retained accounting resolution, not a
claim of literally no work. Tauri's per-run CPU observations span 0.093–0.118%.

### macOS

Run `43579539989`, image `20261104.0514.1`, source `52b840e`, build-input digest
`7850d4cd0f3c…`.

| Candidate | n | Physical footprint, median [range] | Summed RSS, median | Idle CPU, % |
| --- | ---: | ---: | ---: | ---: |
| egui / eframe | 3 | 31.66 [29.35–32.38] | 98.89 | 0.00091 |
| GTK4 + libadwaita | 0 | — live-theme failure; idle refused | — | — |
| Slint | 3 | 16.27 [16.25–16.83] | 97.47 | 0.00105 |
| Qt Widgets | 3 | 28.13 [28.05–29.13] | 101.55 | 0.00067 |
| Tauri | 3 | 44.32 [44.30–44.94] | 147.25 | 0.00938 |

**GTK on macOS.** In all three light-start invocations the light → dark change
repainted within about 2 s, but the following dark → light change did not: the
captured client stayed at luma 40.6 through the eight-second deadline. All three
dark-start invocations failed the same way on their first dark → light change.
In every invocation the application log shows libadwaita's `StyleManager`
reporting the change (`dark=false`), so the application received it; GDK also
logs `gdk_frame_timings_presented() called on skipped frame`, although in the
light-start invocations that warning precedes `dark=false` and accompanies the
change that did repaint. The example uses the standard `connect_dark_notify`
path with no forced palette or timer; in the earlier GTK-only runs listed under
the verification history, an explicit `queue_draw()` did not change the result.
The evidence is consistent with GTK 4.24.1's macOS backend not presenting a
frame after the light-direction style change on this hosted VM, rather than with
a probe fault; the cause is not isolated beyond that. It does not establish that GTK lacks dark appearance
or clipboard support: clipboard acceptance passed in all six invocations.

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

| Environment | Paired n | Primary-memory delta, median [range], MiB |
| --- | ---: | ---: |
| Linux visible, image `20261111.370.1` | 2 | **+4.928 [+1.317–+8.540]** PSS |
| Linux visible, image `20261111.127.1` | 1 | **+0.909** PSS |
| Linux minimized | — | identical to visible per image |
| Windows visible, image `20261112.366.7` | 3 | **+4.641 [+4.480–+4.930]** private working set |
| macOS visible, image `20261104.0514.1` | 3 | **+3.250 [+1.907–+3.938]** physical footprint |

These observations do **not** support an assumed very large resident-memory cost
for enabling the desktop bundle. Linux's wide pair spread (as in the 2026-11-12
run) prevents treating any Linux median as a precise fixed overhead. Three
sequential pairs do not establish statistical significance or a general result
for other machines, renderers or desktop environments. The retained paired JSON
is the authoritative delta source.

## Verification history

[Run 43218424949](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43218424949)
split Linux across images, blocked GTK/macOS on a foreground-verification
disagreement and failed Windows Tauri before its first frame. Runs
[43251948886](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43251948886)
and [43263287428](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43263287428)
completed Linux/Windows but stopped macOS r1/r3 when foreign WebKit helpers left
the reduced control's cleanup unknown. GTK-only macOS runs
[43260869046](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43260869046)
and [43262165209](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43262165209)
isolated the GTK stale frame. All of that evidence is kept at the
`evidence/desktop-import-2026-11-12` tag. The current probe records foreign
helpers instead of stopping. In this run no macOS sequence stopped, but no
foreign helper appeared either (every acceptance row records 0), so the recording
path itself is covered only by host-free tests, not yet by a runner. Selection decisions for all 15 downloaded archives are in
[archives.json](../measurements/desktop-integrated-2026-11-14/archives.json).

## Evidence and reproduction

Use the [runner procedure](github-runners.md) and
[full measurement contract](methodology.md) for setup. The acceptance driver
changes global appearance and replaces the OS clipboard with synthetic text;
run it only in **disposable test desktops**, not an active personal session.
Original appearance is restored, but private clipboard formats and ownership
are not backed up or restored.

After downloading and verifying the selected artifact archives, an import is
reproducible with:

```sh
python3 tools/import_native_run.py 43579539989,43580078566 out/artifacts-current desktop-integrated-2026-11-14
python3 tools/build_desktop_site_data.py measurements/desktop-integrated-2026-11-14
python3 tools/build_desktop_site_data.py measurements/desktop-integrated-2026-11-14 --check
```

`out/artifacts-current` must contain the **nine archives** listed as
`selection: current` in [archives.json](../measurements/desktop-integrated-2026-11-14/archives.json):
six Linux/macOS directories from `43579539989` and three Windows directories from
`43580078566`, named `native-<runner>-<run-id>-r<repetition>`. The importer
retains build versions, outcomes, acceptance records and deterministic compressed
samples under `measurements/native-<run-id>/r<repetition>/<runner>/`, plus r1
light/dark images under `screenshots/`; series CSV/JSON files record eligibility,
exclusions, provenance groups and the paired control. `--check` verifies that the
site's published JSON matches those imported records without rewriting it. A
successful import alone is not an all-jobs-passed claim: review
`import-report.json`, all expected artifacts, acceptance and actual counts.

The [series README](../measurements/desktop-integrated-2026-11-14/README.md) links
the verified original ZIP digests, summaries, acceptance records, paired controls
and retained-file checksums. The import contains **99 outcome records**, **72
requested/measured phase rows**, **29 primary summary groups** and **6
diagnostic-control groups**. These are data-record counts, not 99 successful GUI
tests or 72 independent runner VMs.

## Applicability to Veranda

These examples use **10 synthetic yards / 100 projects without RPC**, and the GTK
example adds libadwaita; they do not measure replacing Veranda's GTK shell. All
three hosted environments render in software (llvmpipe, Microsoft Basic Render
Driver, Apple Software Renderer), so their values do not predict hardware-GPU
memory, latency or battery use. The matched product experiment on real iGPU
hardware is planned in the [roadmap](roadmap.md#hardware-gpu-product-slice).

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
