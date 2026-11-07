# Raw samples — 2026-11-07

The four files are unchanged exports from the original matched UI-only run:

- [egui visible](egui-visible.json)
- [egui minimized](egui-minimized.json)
- [GTK visible](gtk-visible.json)
- [GTK minimized](gtk-minimized.json)

Each JSON contains a `summary` and 121 raw rows: a CPU baseline followed by
120 measured samples. Memory statistics use the 120 post-baseline samples.
Each row contains monotonic time, process ticks/start identity, RSS/PSS in KiB,
guest CPU counters and guest CPU pressure. No credentials, environment dumps or
application/user configuration are included.

CPU percent is `100 * (last_ticks - first_ticks) / 100 / elapsed_seconds` for
the recorded 100 Hz clock. Memory MiB is KiB divided by 1024. P95 uses nearest
rank: sorted index 113 among the 120 measured values. See the
[methodology](../../docs/methodology.md) for scope and limitations.

These samples describe the original measured binaries. Importing their unchanged
source files into this repository does not claim a new measurement run.
