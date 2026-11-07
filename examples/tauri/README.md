# Tauri comparison

Tauri 2.12.5 with `tauri-build` 2.7.4 and a static HTML/CSS/JavaScript frontend.
There is no frontend framework, Node dependency, development server, plugin,
custom IPC command or backend service. Cargo embeds the frontend directly using
the default `custom-protocol` feature.

The system webview is **WebKitGTK on Linux**, **WebView2 on Windows**, and
**WKWebView on macOS**. These are different engines/platform integrations; a
Windows or macOS result is not a WebKitGTK result. Record the installed webview
runtime version as well as Tauri's version.

The initial 1120×768 logical-pixel window shows All projects, project-001 and
snapshot 0. Ten yards and 100 projects support selection/details, an editable
case-sensitive name filter, scrolling and a Refresh snapshot counter. State
stays in JavaScript memory; there are no timers or network calls.

Install Rust and the platform's
[Tauri prerequisites](https://v2.tauri.app/start/prerequisites/), then run from the
repository root:

```sh
cargo build --release --manifest-path examples/tauri/Cargo.toml
cargo run --release --manifest-path examples/tauri/Cargo.toml
```

Neither the Tauri CLI nor npm is needed. The executable is
`veranda-tauri-comparison` (`.exe` on Windows), under
`examples/tauri/target/release` or `$CARGO_TARGET_DIR/release` when set. Its window
title is `Veranda Tauri comparison`; the application identifier is
`org.rustdesktopcomparison.tauri`. Packaging/installers are disabled.

For Debian/Ubuntu, prerequisites include a native compiler, `pkg-config`,
`libwebkit2gtk-4.1-dev`, `libgtk-3-dev`, `librsvg2-dev`,
`libayatana-appindicator3-dev` and `patchelf`. Windows requires MSVC build tools
and the WebView2 runtime; macOS requires Xcode command-line tools.

[frontend/index.html](frontend/index.html) declares the layout,
[frontend/main.js](frontend/main.js) handles fixture state, and
[src/main.rs](src/main.rs) starts the webview. The tiny blue icon is an original
placeholder asset. Dependency licenses are separate from this example's MIT
license; Tauri is [MIT/Apache-2.0](https://github.com/tauri-apps/tauri#licenses),
and system webviews have their own terms.

Resource measurements must include the GUI process **and its webview child
processes**, including helpers with their threads. A single-PID measurement is
not a matched Tauri result. Shared system services and their exclusion must be
documented separately. No historical measurement is claimed for this example.
