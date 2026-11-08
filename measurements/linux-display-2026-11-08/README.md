# Paired Linux display evidence — 2026-11-08

[Report, interpretation and gallery](../../docs/linux-display-comparison.md).

Source commit: `22fb7137a13c78595d4bb366d60e4c859ef57403`.
[Successful run 42502969492](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/42502969492),
Ubuntu 24.04, one runner, all five binaries built once. The run receipt records
successful build, preflight, measurement and artifact-retention steps. The native
watch exited 0; `measurement-receipt.json` records exit 0 and 1570 seconds.

- `results/`: complete original ten-case full-run evidence. Each case has 121 raw
  sample rows (baseline plus 120 intervals), outcome/diagnostic/process records,
  start/end original desktop PNGs, application/display/session logs, and compressed
  original smaps plus per-file grouped resident-memory JSON at both ends.
- `preflight/`: complete original ten short cases, 2-second settle and one interval.
  These are readiness checks, not the values in the report. Their short captures
  can change between endpoints; all full-run endpoint pairs are byte-identical.
- `build/`: original environment, source SHA256 list, build-input verification,
  empty resolution patch and all three exact Cargo locks. Verbose build logs and
  Cargo metadata are retained in the original downloaded CI artifact, not duplicated
  in this curated export.
- `run-view.json` and `measurement-receipt.json`: original completion receipts.
- `derived.csv`: independently recalculated 120-observation RSS/PSS/stat-RSS medians,
  CPU deltas and actual sampling durations; does not round the recorded results.
- `audit.json`: source/binary/PNG/process-scope verification results. Executed source
  hashes match the public files; feature resolution made no changes in this run.
- `SHA256SUMS`: hashes of every copied original file. Generated prose, the derivation
  script and derived outputs are excluded from this original-data manifest.

Recompute and check from the repository root with standard-library Python:

```sh
python3 measurements/linux-display-2026-11-08/derive.py
```

Check preserved bytes from this directory with `sha256sum --check SHA256SUMS`.
The independent derivation verifies both phases, original screenshot hashes,
all 56 raw-smaps/grouped-JSON pairs, app UID 1001 versus reader UID 0, stable
application families, and identical binary hashes across paired cases. It fails
if the current executed source files differ from the recorded source manifest.

The full run uses 30-second settling and 120 approximately one-second intervals.
All short preflights precede the full run, so font/shader caches can be warm. Order
is egui, GTK, Slint, Qt, Tauri, each X11 then native Wayland. There is one visible
960×640 content window on a 1280×720 desktop. Desktop processes are excluded;
Tauri's main, network and web processes are included. CPU is percent of one core;
no counter increment is reported as zero recorded, not an exact absence of work.
