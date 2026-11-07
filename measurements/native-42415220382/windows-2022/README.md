# Windows native samples — retry 42415220382

Original outcome and sample JSON from the completed Windows-only
[retry](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/42415220382),
source commit `a829767517c50b839d7496d009eea815cfac3949`. The first run had no GUI
samples because the probe's Python dependencies were lost after a tool setup step.
This retry fixed interpreter identity and used committed dependency locks.

Slint, Qt Widgets and Tauri have ten-interval diagnostics and 120-interval comparison
samples plus their baselines. Egui has a failed launch outcome, and GTK4 an explicit
`not_run`. No zero-valued comparison result is fabricated for those two cases.

Windows RSS from psutil is Working Set. Tauri's family includes nine observed
processes with WebView2 helpers. Summed resident pages are not deduplicated. CPU
uses observed identity-qualified counter increments and actual monotonic elapsed
time, not an assumed sampling duration. The limitations in each original outcome
remain applicable. Cleanup of tracked processes was clean for the completed attempts.

The [curated report](../../../docs/native-results.md) additionally records manual image
review: captures contain taskbar occlusion and Slint is clipped. Automated
`comparison_passed` statuses are preserved; they do not override that visual limitation
or establish an equal-viewport benchmark. The enclosing retry job failed because
egui's Glow renderer could not initialize a sufficient OpenGL context.

See [the unedited captures](../../../screenshots/native-42415220382/windows-2022/) and
`versions.txt`. Cross-OS and physical-GPU rankings are not established.
