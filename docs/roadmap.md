# Roadmap

Planned work that is not implemented yet. Each item lists what it needs and how
it changes the published comparison.

## Add Iced

- New `examples/iced/` (iced 0.14) with the same fixture: header, Refresh,
  snapshot label, filter, 10 yard buttons, 100 project rows, details column,
  window title `Veranda Iced comparison`, 960×640 client.
- Pin a software renderer (tiny-skia, wgpu disabled) so it compares with Slint's
  software renderer on GPU-less runners; record the renderer in the outcome.
- Add it to the workflow framework list, `run_candidates.py`, `data/features.json`
  (with sources) and the page.

## Startup time

- Probe option `--startup-runs N`: launch N times before the diagnostic, poll for
  the owned visible window every 20 ms (time to window) and for the first
  non-uniform capture (time to first frame, bounded by capture latency), clean the
  process family between launches and require clean cleanup.
- Report the first launch separately from the median of the remaining launches.
- macOS Tauri needs the existing responsibility launcher and external scope for
  every launch, which is the main source of complexity.

## Consistent example layouts

- Replace space-padded "project      NOT_CREATED" labels with real two-column rows
  (Slint `HorizontalLayout` of two `Text`, Qt two-column view or fixed-width labels,
  GTK `GtkBox` with two labels, egui/Tauri fixed column widths).
- Same column offsets, left alignment and row height in every example, so the
  screenshots compare toolkits rather than fixture differences.
- Requires a full re-run because every measured binary changes.

## Further checks

- Verify GTK desktop notifications on Windows/macOS (currently "not verified").
- Distribution size per OS including runtimes (Qt deploy directory, GTK MSYS2
  runtime closure, Homebrew dylibs), not only the executable.
