# Origin and license notices

The initial examples, resource probe, screenshots and measured data were imported
from [Subyard](https://github.com/subyard/subyard), commit
`f0ff6f17f10cb9416fe3fe801a0b53b397bb5a14`.
Original source files are MIT-licensed, copyright (c) 2026 Dmitry Borodin.
The complete original notice is retained in [LICENSES/Subyard-MIT.txt](LICENSES/Subyard-MIT.txt).
This repository's existing [MIT license](LICENSE) is preserved.
Dependency licenses are separate; see each pinned dependency's package metadata.

| Original path | Path here |
| --- | --- |
| `dev/experiments/veranda-gui-comparison/Cargo.toml` | `examples/egui/Cargo.toml` |
| `dev/experiments/veranda-gui-comparison/Cargo.lock` | `examples/egui/Cargo.lock` |
| `dev/experiments/veranda-gui-comparison/src/main.rs` | `examples/egui/src/main.rs` |
| `dev/experiments/veranda-gui-comparison/gtk-control.c` | `examples/gtk/main.c` |
| `dev/experiments/veranda-gui-comparison/measure.py` | `tools/measure.py` |
| `docs/veranda/native-framework-egui.png` | `screenshots/egui.png` |
| `docs/veranda/native-framework-gtk.png` | `screenshots/gtk.png` |

The five source files and both screenshots are byte-identical to the originals.
Names such as Veranda and `org.subyard.Comparison` are retained as provenance of
the synthetic workload, not as a dependency on the Subyard application.
Historical measurements and methodology were adapted from the
[original comparison report](https://github.com/subyard/subyard/blob/f0ff6f17f10cb9416fe3fe801a0b53b397bb5a14/docs/veranda/native-framework-comparison.md).
