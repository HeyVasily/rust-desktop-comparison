#!/usr/bin/env bash
# Run with msys2/setup-msys2's `msys2 {0}` shell, after installing UCRT64
# gcc, pkgconf, gtk4, libadwaita and rust. Keep this runtime private to GTK.
set -euo pipefail

if [[ "${MSYSTEM:-}" != UCRT64 ]]; then
    echo 'GTK Windows setup requires the MSYS2 UCRT64 shell.' >&2
    exit 1
fi

mkdir -p target artifacts/build
pacman -Q > artifacts/build/msys2-packages.txt
{ rustc -Vv; cargo -V; } > artifacts/build/gtk-rust-version.txt
pkg-config --modversion gtk4 libadwaita-1 > artifacts/build/gtk-version.txt

# gtk4-rs links against MSYS2's GTK through pkg-config, so build it with the
# MSYS2 (x86_64-pc-windows-gnu) toolchain in its own target directory.
# GTK_CARGO_FEATURES (e.g. shell-checks) is set only by the shell-integration workflow.
cargo build --release --locked --manifest-path examples/gtk/Cargo.toml \
    --target-dir target/msys2 ${GTK_CARGO_FEATURES:+--features "$GTK_CARGO_FEATURES"} 2>&1 | tee artifacts/build/gtk.log
test -f target/msys2/release/veranda-gtk-comparison.exe

# Forward-slash Windows paths are accepted by the loader and JSON without
# special escaping. The probe must apply this only to the GTK child process.
runtime_bin="$(cygpath -am "$MINGW_PREFIX/bin")"
printf '{"path_prepend":"%s","environment":{"GDK_BACKEND":"win32","GSK_RENDERER":"cairo","GTK_CSD":"0"},"renderer_variant":"GTK4 Cairo software renderer; native decorations; MSYS2 UCRT64; gtk4-rs"}\n' \
    "$runtime_bin" > artifacts/build/windows-gtk-runtime.json
