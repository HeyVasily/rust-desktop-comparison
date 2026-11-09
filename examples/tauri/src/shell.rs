//! Optional shell-integration checks (feature `shell-checks`, env COMPARISON_SHELL_CHECKS).
//! Uses Tauri's own tray, badge and attention APIs plus the official global-shortcut and
//! single-instance plugins.
include!("../../shell_common.rs");

use shell_common::report;
use tauri::image::Image;
use tauri::menu::{Menu, MenuItem};
use tauri::plugin::Builder as PluginBuilder;
use tauri::tray::{MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager, Runtime, UserAttentionType};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

const SHORTCUT: &str = "ctrl+alt+shift+F9";

pub fn install<R: Runtime>(builder: tauri::Builder<R>) -> tauri::Builder<R> {
    if !shell_common::enabled() {
        return builder;
    }
    // The single-instance plugin must be registered first; a second launch exits in it.
    let shortcuts = tauri_plugin_global_shortcut::Builder::new()
        .with_shortcuts([SHORTCUT])
        .expect("parse shortcut")
        .with_handler(|_app, _shortcut, event| {
            if event.state == ShortcutState::Pressed {
                report("hotkey", "event", "Ctrl+Alt+Shift+F9 pressed");
            }
        })
        .build();
    builder
        .plugin(tauri_plugin_single_instance::init(|_app, args, _cwd| {
            report(
                "single-instance",
                "forwarded",
                &format!("{} arguments", args.len()),
            );
        }))
        .plugin(shortcuts)
        .plugin(
            PluginBuilder::<R>::new("shell-checks")
                .setup(|app, _api| {
                    setup(app);
                    Ok(())
                })
                .build(),
        )
}

fn icon() -> Image<'static> {
    let (rgba, width, height) = shell_common::icon_rgba();
    Image::new_owned(rgba, width, height)
}

fn setup<R: Runtime>(app: &AppHandle<R>) {
    report("single-instance", "primary", "tauri-plugin-single-instance");
    match app.global_shortcut().is_registered(SHORTCUT) {
        true => report("hotkey", "registered", "tauri-plugin-global-shortcut"),
        false => report("hotkey", "error", "shortcut not registered"),
    }
    if let Err(error) = tray(app) {
        report("tray", "error", &error.to_string());
    }
    let Some(window) = app.get_webview_window("main") else {
        report("badge", "error", "main window missing");
        return;
    };
    #[cfg(target_os = "windows")]
    let badge = window
        .set_overlay_icon(Some(icon()))
        .map(|_| "set_overlay_icon (Windows has no count badge)");
    #[cfg(not(target_os = "windows"))]
    let badge = window
        .set_badge_count(Some(shell_common::BADGE))
        .map(|_| "set_badge_count");
    match badge {
        Ok(detail) => report("badge", "set", detail),
        Err(error) => report("badge", "error", &error.to_string()),
    }
    std::thread::spawn(move || {
        std::thread::sleep(shell_common::attention_delay());
        match window.request_user_attention(Some(UserAttentionType::Critical)) {
            Ok(()) => report("attention", "requested", "request_user_attention"),
            Err(error) => report("attention", "error", &error.to_string()),
        }
    });
}

fn tray<R: Runtime>(app: &AppHandle<R>) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "show", "Show window", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &quit])?;
    TrayIconBuilder::with_id("shell-check")
        .icon(icon())
        .tooltip(shell_common::TOOLTIP)
        .menu(&menu)
        .on_menu_event(|_app, event| report("tray", "menu", event.id().as_ref()))
        .on_tray_icon_event(|_tray, event| match event {
            TrayIconEvent::Click {
                button,
                button_state: MouseButtonState::Up,
                ..
            } => report("tray", "click", &format!("{button:?}")),
            TrayIconEvent::DoubleClick { button, .. } => {
                report("tray", "click", &format!("double {button:?}"))
            }
            _ => {}
        })
        .build(app)?;
    report("tray", "created", "Tauri TrayIconBuilder");
    Ok(())
}
