# macOS native samples — run 42412948217

Unmodified outcome and sample JSON exported from the completed macOS job in
[GitHub run 42412948217](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/42412948217).
The run used source commit `4dbcf9ca4eeb88f165a1c4363af6a6a44751ac02` and the lockfiles
subsequently preserved in `examples/slint` and `examples/tauri`. Windows/macOS lock
contents were verified equal after normalizing line endings.

Each candidate directory includes `outcome.json` and the raw phase samples. Diagnostic
phases have a baseline and ten intervals; full comparison phases have a baseline and
120 intervals. `family_rss_bytes` is the sum of the observed processes' RSS. CPU uses
observed identity-qualified counter increments, normalized to one logical core.
Short-lived/exiting processes and shared services have the limitations recorded in
the probe outcomes. This is not Linux PSS or a continuous peak measurement.

The [curated report](../../../docs/native-results.md) records manual capture inspection,
actual window-size differences, Qt focus state and GTK's delayed initial paint.
Tauri has diagnostic samples only: process attribution is incomplete, so those values
are not a total application footprint. Raw automated statuses are preserved rather
than rewritten to hide that limitation. The enclosing job was not a full pass.

`versions.txt` records the installed native libraries and compiler. The selected
[unedited captures](../../../screenshots/native-42412948217/macos-15/) are retained
separately, including the initial GTK black client capture.
