#!/usr/bin/env bash
# Run with msys2/setup-msys2's `msys2 {0}` shell, after installing UCRT64
# gcc, pkgconf and gtk4. Keep this runtime private to the GTK candidate.
set -euo pipefail

if [[ "${MSYSTEM:-}" != UCRT64 ]]; then
    echo 'GTK Windows setup requires the MSYS2 UCRT64 shell.' >&2
    exit 1
fi

mkdir -p target artifacts/build
pacman -Q > artifacts/build/msys2-packages.txt
gcc --version > artifacts/build/gtk-compiler.txt
pkg-config --modversion gtk4 > artifacts/build/gtk-version.txt

# Read compiler arguments into arrays; the hosted runner/MSYS2 prefix has no
# spaces. Fail clearly if a custom prefix cannot be represented this way.
if [[ "$PWD" == *' '* || "$MINGW_PREFIX" == *' '* ]]; then
    echo 'Run the GTK comparison in a checkout and MSYS2 prefix without spaces.' >&2
    exit 1
fi
read -r -a gtk_cflags <<< "$(pkg-config --cflags gtk4)"
read -r -a gtk_libs <<< "$(pkg-config --libs gtk4)"
gcc -O2 -Wall -Wextra "${gtk_cflags[@]}" examples/gtk/main.c \
    -o target/gtk-control.exe "${gtk_libs[@]}" 2>&1 | tee artifacts/build/gtk.log

# Forward-slash Windows paths are accepted by the loader and JSON without
# special escaping. The probe must apply this only to the GTK child process.
runtime_bin="$(cygpath -am "$MINGW_PREFIX/bin")"
printf '{"path_prepend":"%s","environment":{"GDK_BACKEND":"win32","GSK_RENDERER":"cairo","GTK_CSD":"0"},"renderer_variant":"GTK4 Cairo software renderer; native decorations; MSYS2 UCRT64"}\n' \
    "$runtime_bin" > artifacts/build/windows-gtk-runtime.json
