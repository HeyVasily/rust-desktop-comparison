# Desktop-integrated evidence — 2026-11-12

These are retained outputs from the repository's **GitHub Actions runs**,
re-imported and checked on 2026-11-12. They are not new local application runs,
physical-iGPU measurements, or a production Veranda benchmark. The fixture is
10 synthetic yards / 100 projects with no RPC backend, in release builds.

Read the [results and limitations](../../docs/desktop-results.md) before comparing
numbers. The source used to build each application is recorded independently of
the later commit that publishes this evidence.

## Selected cohorts

| Platform | Run and measured source | Selected artifacts | Eligible memory observations |
| --- | --- | --- | --- |
| Linux | [43251948886](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43251948886), `fe53a64d6759b17817d4cc1c5c995b43a8031d5c` | `native-ubuntu-24.04-43251948886-r1`, `-r2`, `-r3` | All five desktop profiles, n=3 visible and n=3 minimized each |
| Windows | Same run and source | `native-windows-2022-43251948886-r1`, `-r2`, `-r3` | All five desktop profiles, n=3 visible each |
| macOS | [43263287428](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43263287428), `589a6111d79156d787471069aa9e26d5b289d5d7` | `native-macos-15-43263287428-r1`, `-r2`, `-r3` | egui, Slint, Qt and Tauri, n=1 visible each (r2); GTK excluded |

The six selected Linux/Windows jobs passed. Both overall workflow runs concluded
**failure**. The macOS jobs did not pass the complete profile: GTK failed live
theme transitions; r1/r3 stopped their normal sequence when process ownership
was unresolved after the reduced control. Their separate dark-start sequence
ran for all five candidates. Four candidates passed those dark checks, while
GTK failed in all three repetitions.

No missing light-start run is filled with a dark-start smoke result. One valid
memory observation remains n=1. `fully_verified` additionally requires matching
light/dark repetition sets without duplicate cases within the same provenance
group. The current macOS series therefore remains incomplete or failed even
where its individual observations are usable.

## Retained data

- [summary.csv](summary.csv): eligible primary observations, separately grouped
  by source, build, image, run, profile, metric and visible/minimized phase.
- [runs.csv](runs.csv): all 62 requested/measured phase records, including the
  three excluded phases and their reasons. This is not a count of independent VMs.
- [desktop-acceptance.csv](desktop-acceptance.csv): all 89 selected outcome
  records, including separate dark-start checks and reduced controls.
- [controls.csv](controls.csv): diagnostic reduced-profile aggregates, excluded
  from the main desktop ranking.
- [paired-egui-ab.json](paired-egui-ab.json): same-run/source/repetition paired
  deltas, with missing or ineligible counterparts retained as unpaired.
- [import-report.json](import-report.json): 9 selected artifacts, 19 primary
  summary groups, 4 control groups and explicit exclusions.
- [archives.json](archives.json): original artifact IDs, download endpoints,
  GitHub SHA-256 digests and the selection decision for all 11 downloaded ZIPs.
- [workflow-runs.json](workflow-runs.json): fetched workflow/job conclusions,
  source commits and URLs. A successful import is not a successful workflow.
- [SHA256SUMS](SHA256SUMS): checksums of the six generated series data files.
- [EVIDENCE-SHA256SUMS](EVIDENCE-SHA256SUMS): repository-relative hashes of retained
  native evidence plus the archive and workflow receipts.

All 11 original ZIP downloads matched their GitHub-published SHA-256 digests
before extraction. The original ZIPs are not duplicated in Git. The retained
contents remain available after Actions' artifact expiry; sample JSON is
compressed deterministically with no timestamp or embedded gzip filename.

The raw directories contain outcomes, captures, application logs, raw samples,
source manifests, lockfiles, feature trees, compiler/native-runtime versions and
executable hashes:

- [Linux/Windows current evidence](../native-43251948886/).
- [Final macOS evidence](../native-43263287428/).
- [Earlier macOS r1](../native-43251948886/r1/macos-15/) and
  [r2](../native-43251948886/r2/macos-15/) are diagnostic history. Their archives
  have `selection: diagnostic-history` and do **not** enter this series. The
  earlier run's macOS r3 was canceled without an artifact.

The two macOS reduced-control exclusions list newly observed, unassigned WebKit
helpers with `cleanup_status=unknown` and an empty `cleanup_survivors` list. They
do not prove that egui spawned WebKit or leaked an owned process. The incomplete
ownership result remains excluded without inventing an attribution.

## Reproduction

Download the artifacts identified in `archives.json`, verify each original ZIP
against its `digest`, and extract **only the nine `selection: current` archives**
into `out/artifacts-current`, preserving their complete artifact directory names.
Keep the two diagnostic-history directories outside that importer input.

From the repository root:

```sh
python3 tools/import_native_run.py 43251948886,43263287428 out/artifacts-current desktop-integrated-2026-11-12
python3 tools/build_desktop_site_data.py measurements/desktop-integrated-2026-11-12
python3 tools/build_desktop_site_data.py measurements/desktop-integrated-2026-11-12 --check
sha256sum --check measurements/desktop-integrated-2026-11-12/EVIDENCE-SHA256SUMS
```

The importer verifies raw process-family samples, CPU counters, elapsed time,
summary statistics, process cleanup, accepted window identity and retained
screenshots. It does not regenerate native application measurements.

An independent recalculation of the GTK/egui subset checked 19 eligible phases
and 2,299 raw samples (baseline plus 120 intervals per phase), with no mismatch
against the stored process sums, medians, p95, CPU or aggregate tables.
Representative captures were visually reviewed across all five candidates:
Linux r1, Windows r1 and macOS r2. GTK's stale macOS light-transition capture
visibly supports its failed acceptance; successful idle captures show the restored
fixture. This is a stated visual sample, not a claim to have manually reviewed
every image.

## Outstanding product evidence

Linux here is X11/Xvfb with llvmpipe; Windows egui uses Microsoft Basic Render
Driver; macOS egui reports Apple Software Renderer. Native Wayland acceptance of
these updated profiles, hardware-iGPU operation, full IME/accessibility, real
Veranda RPC 20/200, startup p95, burst/reconnect and 100-cycle resource retention
remain separate work. See the [product-specific follow-up](../../docs/desktop-results.md#applicability-to-veranda-and-the-hardware-follow-up).
