# Linux native samples — run 42412948217

Unmodified outcomes and raw sample JSON from the successful Ubuntu 24.04 job in
[run 42412948217](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/42412948217/job/128524807125).
Source commit `4dbcf9ca4eeb88f165a1c4363af6a6a44751ac02`. Generated Slint/Tauri locks
match the lockfiles subsequently committed to the examples, after newline normalization.

All five candidates have a diagnostic baseline plus ten intervals, and full visible
and minimized baselines plus 120 intervals each. The initial UI has project-001 and
snapshot 0, with no automated interaction/focus normalization. Minimized X11 state
was verified before and after sampling. Tracked-process cleanup was clean.

RSS is the observed process-family resident sum, including Tauri's webview helpers;
shared pages are not deduplicated. This is not Linux PSS. CPU uses identity-qualified
counter increments and actual monotonic elapsed time. Process discovery can miss
very short-lived children or the final CPU interval of exiting processes. See each
outcome's scope limits and the [curated report](../../../docs/native-results.md).

`versions.txt` preserves compiler, native library and GLX/Mesa versions. The
[unedited visible client captures](../../../screenshots/native-42412948217/ubuntu-24.04/)
were visually inspected; each is 1120×768. This new Ubuntu series is separate from
the historical patched/full-backend results and the earlier Debian Cairo-requested pair.
