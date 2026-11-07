# Qt Widgets comparison

A standalone C++17 control using Qt 6 Widgets. No Qt Quick, QML, WebEngine or Rust
bindings are involved. CMake accepts Qt 6.4 or newer; record the installed Qt version
alongside any measurement instead of treating the minimum as the measured version.

The initial 1120×768 logical-pixel window shows All projects, project-001 and
snapshot 0. It includes ten yard buttons, 100 selectable project rows, details,
an editable case-sensitive name filter, scrolling and an in-memory Refresh counter.
There is no backend or timer.

From the repository root, with CMake, a C++ compiler and Qt 6 Widgets development
packages installed:

```sh
cmake -S examples/qt -B target/qt -DCMAKE_BUILD_TYPE=Release
cmake --build target/qt --config Release
```

Run `target/qt/veranda-qt-comparison`; Visual Studio generators normally place the
Windows executable at `target/qt/Release/veranda-qt-comparison.exe`. The window
title is `Veranda Qt Widgets comparison`. The target is a plain executable on
macOS, not an app bundle.

On Debian, install `build-essential cmake qt6-base-dev`. On Windows, use the
matching Qt MSVC kit and Visual Studio C++ tools. On macOS, use the macOS Qt kit
and Xcode command-line tools. Set `CMAKE_PREFIX_PATH` to the Qt kit prefix if CMake
cannot discover it. Qt's DLLs/frameworks and platform plugins must be reachable at
runtime; on Windows run `windeployqt` from the same kit on the built executable
before moving it outside the build environment.

[main.cpp](main.cpp) contains the complete widget tree and event connections.
This source is independent of the historical Qt frontend; earlier measurements
do not measure this program. Qt retains its own
[licensing terms](https://doc.qt.io/qt-6/licensing.html).
