# GTK Linux memory A/B — 2026-11-08

See the [combined report](../../docs/gtk-memory-investigation.md), including real
screenshots, mapping attribution and limits on the historical comparison.

| Environment | Cases | Evidence |
| --- | --- | --- |
| Debian 13 / GTK 4.18.6 | X11 and Wayland × default/Cairo; conditional X11/Cairo with GL/Vulkan disabled | [Five cases](debian-13/README.md) |
| Ubuntu 24.04 / GTK 4.14.5 | X11 default/Cairo, same hosted runner and binary | [Two cases](ubuntu-24.04/README.md) |

These additive measurements preserve all previous raw series. They use the same
C source/probe bytes, one build per environment, an opt-in after-paint renderer
log, 30-second settling and 120 measured intervals. Runtime versions and actual
renderers are observations, not inferred from requested environment variables.
