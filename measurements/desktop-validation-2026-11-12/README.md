# Desktop validation failures retained for review

These are **failed checks**, not a current memory ranking or passed desktop
acceptance. They are preserved byte-for-byte from the verified artifacts of
[run 43218424949](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/43218424949)
at source [76bc29b](https://github.com/HeyVasily/rust-desktop-comparison/commit/76bc29baa329bbc0843b2d294a45f7df04c824e3).
The complete original artifacts included successful candidates too; only the
five failed cases are retained here. Their archive identifiers and verified
SHA-256 digests are in [archives.json](archives.json).

| Case | Repetitions retained | Observed failure |
| --- | --- | --- |
| GTK4 + libadwaita / macOS | 1, 2, 3 | The activation request returned, but the actual foreground PID stayed different; theme and clipboard checks were not run. |
| Tauri / Windows | 1, 3 | The first-frame check still saw blank white content at its eight-second deadline; subsequent live-theme and clipboard checks passed, but startup failure invalidated the invocation. |

Every directory retains the original `outcome.json`,
`desktop-integration.json`, application log and available captures. There are
no invented screenshots for the macOS cases: they failed before capture. The
Windows `desktop-startup.png` files are genuinely blank failure evidence, not
successful light-theme renders.

The fixes add bounded native exact-PID activation plus independent focus
verification on macOS, and separate first-render readiness (30 seconds for every
candidate) from the unchanged eight-second live-theme deadline. Later success
must come from a new run, not from reclassifying these failures.

See the [current desktop results and verification history](../../docs/desktop-results.md).
