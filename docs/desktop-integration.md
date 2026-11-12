# Desktop-integrated baseline

The primary desktop configuration must be usable as a desktop application, not
just draw the fixture. Framework capability, enabled build features, exercised
behavior and measured resource cost are four separate claims. This page defines
the profile and the evidence needed to connect them.

The [desktop results report](desktop-results.md) records the measurement revision,
observed versions, actual acceptance outcomes and paired egui control; this page
specifies what the profile requires, not which run passed it.

The [2026-11-09 native matrix](full-native-results.md) remains a **historical
UI-only baseline**. It measured the process family before an external clipboard
check and used a relaunch-only system-theme check. Do not attribute those numbers
or its screenshots to the current integrated binaries.

## What the desktop profile includes

| Requirement | What must be present | What demonstrates it |
| --- | --- | --- |
| System appearance at startup | Read the OS preference rather than hard-code light/dark | Verify the external OS setting and capture the client after launch |
| Live appearance changes | React to system changes without restarting or periodic polling | Keep the same process alive through light → dark → light, retaining captures and process identity |
| System text clipboard | The real platform clipboard, not an internal application buffer | External process → editable filter paste, then filter → external process copy with exact Unicode comparison |
| Desktop text stack | Bundled fonts plus system-font fallback where applicable; existing IME/accessibility integration retained | Preserve the resolved feature tree; do not equate a Unicode clipboard test with full IME, font or screen-reader qualification |
| Normal window backends | Native Windows/macOS backends; both X11 and Wayland compiled for Linux where supported | Record the actual display backend, renderer and toolkit versions for each run |
| Idle behavior after use | Integration services stay enabled after exercising them | Restore empty filter and unfocused controls, settle, then sample the same app process family |

This is a desktop **baseline**, not a complete production application. There is
still no RPC/backend, disk inventory, notification stream or periodic workload.
Those product-specific costs must be measured in the actual product.

## Feature configuration

The historical egui example specified `default-features = false` and re-enabled
accessibility, fonts, selected renderers and display backends. In **eframe
0.37.0**, `clipboard`, `links` and `system_fonts` are distinct default features;
they were not automatically restored by that list.

In particular, eframe explicitly documents that disabling `clipboard` leaves a
simulated in-application clipboard. Copying and pasting inside one egui window
therefore cannot prove OS interoperability. An `arboard` entry in `Cargo.lock`
also cannot establish which feature was built: the resolved, target-specific
feature graph and an external-process test are required.

The default desktop build now explicitly includes:

- `clipboard`: OS clipboard through egui-winit and its platform adapters;
- `links`: the normal open-in-browser integration;
- `system_fonts`: on-demand fallback to installed fonts for missing characters;
- the existing `accesskit` and `default_fonts` features;
- Glow on Linux/macOS, WGPU/DX12 on the existing Windows runner configuration;
- both `x11` and `wayland` on Linux;
- an event-driven Linux Settings portal bridge for system appearance. Native
  Windows/macOS theme input continues through winit.

Sources: the pinned [eframe 0.37.0 feature definitions](https://github.com/emilk/egui/blob/0.37.0/crates/eframe/Cargo.toml),
[egui-winit integration](https://github.com/emilk/egui/blob/0.37.0/crates/egui-winit/Cargo.toml),
and the [example manifest](../examples/egui/Cargo.toml).

Enabling these features can add code, resident pages, caches or threads. How much
it adds is a measurement question. Neither the number of dependencies nor the
executable-size change predicts the warmed resident-memory delta.

The GTK default profile is **GTK4 + libadwaita**, not bare GTK4. It enables the
`desktop` feature, includes the `libadwaita` Rust bindings pinned to `0.9.2`,
initializes libadwaita and uses `AdwStyleManager` with the default system-driven
color scheme. The native libadwaita library is an additional runtime dependency;
its mappings are part of the application process and must be included in memory
measurements. Record its installed version separately from the Rust bindings.
The historical GTK captures and figures came from bare GTK and must retain that
label. See the [GTK manifest](../examples/gtk/Cargo.toml),
[startup integration](../examples/gtk/src/main.rs), and
[StyleManager API](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/main/class.StyleManager.html).

On macOS, the integrated GTK example additionally queues one window redraw on
each real `AdwStyleManager::dark` notification, using a weak window reference.
This addresses a stale-frame symptom observed with GTK 4.24.1/libadwaita 1.10.0:
the OS and style manager changed back to light, while the captured client stayed
dark until ordinary keyboard input. The application does not force a palette,
poll the preference or continuously repaint; it uses GTK's
[normal redraw invalidation](https://docs.gtk.org/gtk4/method.Widget.queue_draw.html).
Theme notifications include monotonic elapsed timestamps for diagnosis. This
workaround is part of the measured macOS desktop profile; only fresh external
acceptance results can establish whether it resolves the observed failure.

For egui and GTK, `--no-default-features` is an explicitly reduced diagnostic
control, not the published normal desktop profile.

The Windows Qt profile selects the built-in **Fusion** widget style while keeping
the native Windows platform plugin and its system palette. Qt's legacy Vista
style deliberately substitutes light colors even with a dark OS preference;
that is a style limitation, not absent dark rendering throughout Qt. Fusion is a
documented deployment choice, not a hand-written dark palette or native Win32
control styling. macOS retains its native Qt style. See the
[Qt profile notes](../examples/qt/README.md#normal-desktop-integration).

## Appearance is three different checks

1. **Light/dark rendering:** does the toolkit/application have both palettes?
2. **System preference at launch:** does the example choose the requested palette?
3. **Live updates:** does an already running example change when the OS setting
   changes, and change back?

Both egui and GTK support light/dark rendering. A failed historical startup
check does not mean either lacks dark mode. GTK settings, libadwaita's
`AdwStyleManager` and application-specific bridges are different integration
routes; the report must name which one was built, its versions and platforms.
For a raw-GTK app, merely setting a dark-style preference once is not a live OS
subscription.

On Linux, the desktop setting, Settings portal and application's display
connection must belong to the same session. The probe must verify that the
portal reports the requested preference; a successful `gsettings` command alone
is insufficient. An unavailable portal is an integration/environment limitation,
not an implicit pass. Fallback colors are useful application behavior but do not
qualify system-theme following.

The current CI environment is a named **GNOME-like X11/Adwaita** profile, not a
claim about all Linux desktops. It runs the real `gsd-xsettings` daemon and sets
both the modern portal preference and the shared GTK3 theme
(`Adwaita` / `Adwaita-dark`) for every candidate. The latter matters for Qt's GTK3
theme plugin: the plugin may observe the dark preference while still receiving
light brushes from an unchanged GTK3 theme. The driver independently verifies
both the portal and effective GTK3 settings, and restores both original keys.
No application receives a hand-written palette or a candidate-specific theme
override. See the [Qt deployment notes](../examples/qt/README.md) for sources and
the distinction from stock GNOME and other desktop settings UIs.

Palette classification uses the client area, not just the titlebar. Captures,
luminance values and timing are retained so a reviewer can detect blank windows,
occlusion, an unchanged palette or a failed setting change. No theme switch may
restart the app used by the live-change or post-exercise memory check.

## Clipboard acceptance

The probe uses the ordinary filter widget and platform keyboard shortcuts. It
places known Unicode text in the OS clipboard from an external process, pastes
it into the widget, then replaces the external clipboard with a different
sentinel before copying from the widget. The final externally read text must
match the original exactly. This prevents a missing paste/copy path from passing
because the clipboard happened to contain the expected string already.

Afterward the filter and focus state are restored before idle sampling. Clipboard
test helpers are not counted as application processes, and the evidence must
identify cleanup, failures and platform-specific omissions. X11 `CLIPBOARD`,
X11 primary selection, Wayland selections and persistence after the application
exits are different behaviors; passing the tested text path does not establish
all of them. Images, HTML and arbitrary MIME types are outside this baseline.

## Measuring the integration cost

For every integrated result, retain the source commit, complete lockfile, enabled
target feature tree, compiler/toolkit versions, binary hash, display/renderer,
OS setting, acceptance outcome, captures and raw resource samples. Sampling
uses the existing application-family scope and per-platform primary metric:
Linux PSS, Windows private working set, macOS physical footprint. Thread stacks
and in-process integration allocations belong to the measured application.

A valid primary desktop result requires acceptance to pass **before** memory
sampling. Failed, unsupported, not-run and environment-blocked checks must remain
distinguishable; none can silently become a green tick or a zero-memory result.
Clear and unfocus the editor, restore the same palette and fixture state, and
use the same settling/sampling policy for all candidates.

`tools/native_probe.py --desktop-checks --startup-theme light` records
`measurement_profile: desktop-integrated` and a structured `desktop_integration`
outcome in the native result, with a standalone `desktop-integration.json` and
startup/live/clipboard screenshots. The gate records `passed`, `failed`,
`environment_error` or `not_run`, the same window/process identity, the observed
OS setting, client luminance and exact copied text. A run without these checks
is labeled `legacy-ui-only`. The current Linux automated keyboard/clipboard
driver covers **X11**, not native Wayland; unsupported driver coverage must not
be presented as missing toolkit capability. See the
[probe implementation](../tools/desktop_probe.py).

To measure an egui profile difference, build both a diagnostic reduced-feature
control and the desktop profile with the same toolchain on the same host. Keep
renderer, display session, installed fonts, final light palette, window geometry,
fixture state and settling/sampling policy constant; alternate run order and
publish each repetition. The reduced control's OS light preference is verified
before and after sampling, but it does not pass desktop acceptance.

The warmed workloads are deliberately **not identical**: only the integrated
profile exercises external clipboard and live system-theme changes, which the
reduced build cannot support. The delta therefore describes the whole configured
profile after use, including retained allocations and caches, not the allocation
of an individual feature or dependency. The control is neither a recommendation
nor part of the primary ranking. Comparing a fresh local result to an old
hosted-runner median is not a matched A/B experiment. Report executable size
separately from memory.

The application-family scope excludes shared desktop services such as the
compositor, session bus, XSettings daemon and Settings portal. Record required services and any
newly started helpers; do not silently charge a shared service once per toolkit
or treat its exclusion as a zero-cost claim. Accessibility clients and font
caches can also change a warmed app's footprint.

## Evidence and remaining coverage

The historical startup results are preserved with explicit **Passed stated
test / Failed stated test** labels in the [feature matrix](features.md). They
do not qualify the new desktop profile. Fresh results must identify their own
profile, source revision, operating system and display backend; a successful
build or a test of the source alone does not supply a footprint result.

The following remain separate from the baseline unless a run explicitly includes
them:

- [Optional shell checks](shell-integration.md): tray, badges, global shortcuts
  and single-instance integration; the historical memory matrix did not build
  that feature set. A tray-dependent product needs another warmed profile.
- Native menus, file pickers, notifications, credential-store access, autostart,
  URL/file associations and installed-bundle behavior.
- End-to-end screen-reader navigation, IME composition/dead keys, mixed-DPI
  monitor transitions, fractional scaling and glyph coverage.
- Clipboard persistence after exit, image/MIME transfer, primary selection and
  every Wayland compositor/backend combination.
- Hardware-GPU behavior, startup/interaction latency, suspended/minimized wakeups
  and the real application's backend load.

These gaps belong in the comparison alongside the memory numbers, not in an
assumption that a small example exercises every available desktop facility.
