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

## Linux display and renderer in the main matrix

The [X11/Wayland](linux-display-comparison.md) and [GTK renderer](gtk-memory-investigation.md)
series still use the GTK C control (`examples/gtk-c`). Next: add the same
`DISPLAY_DIAGNOSTIC` report to the gtk4-rs example, switch both workflows to it, and
add a native Wayland pass (and a `GSK_RENDERER=cairo` variant) to the repeated native
matrix. Fold the X11/Wayland split from [platform-support.md](platform-support.md)
into `data/features.json` so there is one feature matrix.

## Shell integration follow-ups

The [runner checks](shell-integration.md) leave gaps: macOS tray clicks (need an
Accessibility-enabled runner), Wayland (tray hosts, the GlobalShortcuts portal,
xdg-activation), autostart, URL schemes and file associations (need installed
bundles), and the open causes of two failures — GTK's global shortcut on macOS and
Qt 6.4's attention request on X11. Repeating the run would also show whether any
result is flaky.

## Further checks

- Verify GTK desktop notifications on Windows/macOS (currently "not verified").
- Distribution size per OS including runtimes (Qt deploy directory, GTK MSYS2
  runtime closure, Homebrew dylibs), not only the executable.

## Hardware-GPU product slice

- A read-only egui fleet view on Veranda's existing Rust client/store and
  unchanged RPC contract, beside the existing GTK view, with the real
  20-yard / 200-project inventory. No polling or new authority.
- Run on a user desktop with a verified hardware GPU (including integrated
  graphics); the application must report the adapter it actually used.
- Accept input, clipboard, accessibility and HiDPI first, then compare visible and
  minimized idle, startup, event bursts, sleep/reconnect and 100 connection cycles.
- The existing GTK harness (`dev/e2e/veranda-wayland-resources.py` in Subyard)
  covers the GTK side; its readiness and input steps need an egui adapter.

## GTK live light repaint on macOS

The 2026-11-14 run fails GTK 4.24.1 on macOS in all six invocations: libadwaita
reports the dark → light change, GDK logs a skipped frame, and the window stays
dark until input. Reduce it to a plain GTK4 sample without libadwaita, report it
upstream if it reproduces, and rerun GTK-only macOS acceptance on the next GTK
release. No app-side repaint workaround: it would no longer test the system path.
