# Slint comparison

Stock Slint 1.18.1, Rust and a small declarative layout. The example selects the
winit backend and software renderer explicitly. Accessibility is enabled; the
Qt backend, GPU renderers and local dependency patches are absent.

The initial 1120×768 logical-pixel window shows All projects, project-001 and
snapshot 0. Ten yard buttons filter 100 synthetic projects. Project buttons update
details, the editable filter matches project names, the list scrolls, and Refresh
increments the in-memory snapshot. There is no backend or periodic work.

From the repository root, with a current Rust toolchain and native compiler:

```sh
cargo build --release --manifest-path examples/slint/Cargo.toml
cargo run --release --manifest-path examples/slint/Cargo.toml
```

The binary is `veranda-slint-comparison` (`.exe` on Windows), under
`examples/slint/target/release` or `$CARGO_TARGET_DIR/release` when that variable
is set. The window title is `Veranda Slint comparison`.

Windows uses the MSVC build tools; macOS uses Xcode command-line tools. On Linux,
install a native compiler, `pkg-config`, fontconfig, and the X11/Wayland development
libraries used by winit (on Debian: `build-essential pkg-config libfontconfig1-dev
libxkbcommon-dev libxkbcommon-x11-dev libx11-dev libxcb1-dev libwayland-dev`).
Run in a graphical desktop session with its session bus and accessibility service.

The layout is in [ui/main.slint](ui/main.slint), with model and event wiring in
[src/main.rs](src/main.rs). This new stock build is distinct from the historical
patched Slint frontend and has no inherited measurement results.

Slint's dependencies retain their own licenses; see the upstream
[licensing options](https://slint.dev/license/) and
[backend documentation](https://docs.slint.dev/latest/docs/slint/guide/backends-and-renderers/backend_winit/).
