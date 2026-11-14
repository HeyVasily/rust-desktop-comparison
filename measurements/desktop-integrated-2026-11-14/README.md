# Desktop-integrated evidence — 2026-11-14

These are retained outputs from the repository's **GitHub Actions runs**,
imported and checked on 2026-11-14. They are not local application runs,
physical-iGPU measurements, or a production Veranda benchmark. The fixture is
10 synthetic yards / 100 projects with no RPC backend, in release builds.

Read the [results and limitations](../../docs/desktop-results.md) before comparing
numbers. The source used to build each application is recorded independently of
the later commit that publishes this evidence.

## Selected cohorts

| Platform | Run and measured source | Selected artifacts | Eligible memory observations |
| --- | --- | --- | --- |
| Linux | [43579539989](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43579539989), `52b840ef822f4af41d713b5541fb49ba2cab5923` | `native-ubuntu-24.04-43579539989-r1`, `-r2`, `-r3` | All five desktop profiles, visible and minimized; n=1 on image `20261111.127.1` plus n=2 on `20261111.370.1` |
| Windows | [43580078566](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43580078566), `d1b3951dde8d17761509f8d5b383fa1c153a9a43` | `native-windows-2022-43580078566-r1`, `-r2`, `-r3` | All five desktop profiles, n=3 visible |
| macOS | [43579539989](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43579539989), `52b840ef822f4af41d713b5541fb49ba2cab5923` | `native-macos-15-43579539989-r1`, `-r2`, `-r3` | egui, Slint, Qt and Tauri, n=3 visible; GTK excluded |

All six Linux/Windows jobs passed. The three macOS jobs failed only on the gate
requiring every configured candidate: GTK failed live-theme acceptance in all
three light-start and all three dark-start invocations. Every other macOS
candidate passed light-start, dark-start, clipboard and cleanup in r1/r2/r3.
No sequence stopped early, and no foreign WebKit helper was observed.

`fully_verified` requires matching light/dark repetition sets without duplicate
cases within one provenance group. The two Linux image groups are each fully
verified at their own n; they are never pooled.

## Retained data

- [summary.csv](summary.csv): eligible primary observations, separately grouped
  by source, build, image, run, profile, metric and visible/minimized phase;
  `failed_repetitions` includes selected candidates a stopped sequence never ran.
- [runs.csv](runs.csv): all 72 requested/measured phase records, including the
  three excluded GTK/macOS phases and their reasons. This is not a count of VMs.
- [desktop-acceptance.csv](desktop-acceptance.csv): all 99 selected outcome
  records, including separate dark-start checks, reduced controls and the count
  of foreign WebKit helpers per invocation.
- [controls.csv](controls.csv): diagnostic reduced-profile aggregates, excluded
  from the main desktop ranking.
- [paired-egui-ab.json](paired-egui-ab.json): same-run/source/repetition paired
  deltas, with missing or ineligible counterparts retained as unpaired.
- [import-report.json](import-report.json): 9 selected artifacts, 29 primary
  summary groups, 6 control groups, explicit exclusions and the (here empty)
  list of failed repetitions that could not be attributed to an image.
- [archives.json](archives.json): original artifact IDs, download endpoints,
  GitHub SHA-256 digests and the selection decision for all 15 downloaded ZIPs.
- [workflow-runs.json](workflow-runs.json): fetched workflow/job conclusions,
  source commits and URLs for all three runs. A successful import is not a
  successful workflow.
- [SHA256SUMS](SHA256SUMS): checksums of the six generated series data files.
- [EVIDENCE-SHA256SUMS](EVIDENCE-SHA256SUMS): repository-relative hashes of retained
  native evidence plus the archive and workflow receipts.

Not selected, with reasons in `archives.json`:

- `native-windows-2022-43579539989-r1..r3`: the regression-test step failed
  (POSIX-only site smoke tests) before any build; replaced by run 43580078566.
- `native-ubuntu-24.04-43583529539-r1..r3`: a Linux rerun meant to land all
  three repetitions on one image; it split as well (r1/r2 `…370.1`, r3 `…127.1`),
  so 43579539989 was kept. For the same Qt executable it measured Qt PSS of
  36.75–37.20 MiB against 42.55–42.59 MiB here; the other four candidates agree
  within 2 MiB. The Linux Qt figure is therefore run-dependent; see the
  [results](../../docs/desktop-results.md#linux-x11--adwaita--llvmpipe).

All 15 original ZIP downloads matched their GitHub-published SHA-256 digests
before extraction. The original ZIPs are not duplicated in Git; sample JSON is
compressed deterministically with no timestamp or embedded gzip filename.

The retained directories contain outcomes, desktop-acceptance records,
application logs, raw samples, source manifests, compiler/native-runtime versions
and executable hashes. Per-invocation captures, resolved feature graphs and
lockfile copies are not retained: the importer verifies captures against the
recorded luminance while reading the archive, `build/inputs-sha256.json` keeps
the per-file digests behind each group's `build_inputs_sha256`, and repetition
1's light/dark comparison images are kept under `screenshots/native-<run-id>/<runner>/`.

- [Linux/macOS evidence](../native-43579539989/) and
  [screenshots](../../screenshots/native-43579539989/).
- [Windows evidence](../native-43580078566/) and
  [screenshots](../../screenshots/native-43580078566/).

The previous import (runs 43251948886/43263287428, every capture and feature
graph) is preserved at tag
[`evidence/desktop-import-2026-11-12`](https://github.com/HeyVasily/rust-desktop-comparison/tree/evidence/desktop-import-2026-11-12/measurements).

## Reproduction

Download the artifacts identified in `archives.json`, verify each original ZIP
against its `digest`, and extract **only the nine `selection: current` archives**
into `out/artifacts-current`, preserving their complete artifact directory names.

From the repository root:

```sh
python3 tools/import_native_run.py 43579539989,43580078566 out/artifacts-current desktop-integrated-2026-11-14
python3 tools/build_desktop_site_data.py measurements/desktop-integrated-2026-11-14
python3 tools/build_desktop_site_data.py measurements/desktop-integrated-2026-11-14 --check
sha256sum --check measurements/desktop-integrated-2026-11-14/EVIDENCE-SHA256SUMS
```

The importer verifies raw process-family samples, CPU counters, elapsed time,
summary statistics, process cleanup, accepted window identity and capture
luminance in the archive. It does not regenerate native application measurements.

## Outstanding product evidence

Linux here is X11/Xvfb with llvmpipe; Windows egui uses Microsoft Basic Render
Driver; macOS egui reports Apple Software Renderer. Native Wayland acceptance of
these updated profiles, hardware-iGPU operation, full IME/accessibility, real
Veranda RPC 20/200, startup p95, burst/reconnect and 100-cycle resource retention
remain separate work. See the [product-specific follow-up](../../docs/desktop-results.md#applicability-to-veranda).
