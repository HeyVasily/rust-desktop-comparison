//! Optional shell-integration checks (feature `shell-checks`, env COMPARISON_SHELL_CHECKS).
//! Single instance uses GApplication's own uniqueness rather than a crate.
include!("../../shell_common.rs");
include!("../../shell_crates.rs");
include!("../../shell_tray_crate.rs");

use gtk::prelude::*;
use gtk::{Application, ApplicationWindow, glib};
use shell_common::report;

pub struct Shell {
    _tray: Option<tray_icon::TrayIcon>,
    _hotkey: Option<global_hotkey::GlobalHotKeyManager>,
}

/// Returns true when an earlier activation already built the window: a second launch
/// was forwarded to this primary instance by GApplication.
pub fn forwarded_activation(app: &Application) -> bool {
    if !shell_common::enabled() {
        return false;
    }
    if let Some(window) = app.active_window() {
        report(
            "single-instance",
            "forwarded",
            "GApplication activate from a second launch",
        );
        window.present();
        return true;
    }
    report(
        "single-instance",
        if app.is_remote() { "remote" } else { "primary" },
        "GApplication",
    );
    false
}

pub fn start(window: &ApplicationWindow) -> Option<Shell> {
    if !shell_common::enabled() {
        return None;
    }
    report("badge", "no-api", "GTK 4 has no Dock or taskbar badge API");
    let weak = window.downgrade();
    glib::timeout_add_local_once(shell_common::attention_delay(), move || {
        if let Some(window) = weak.upgrade() {
            request_attention(&window);
        }
    });
    Some(Shell {
        _tray: shell_tray_crate::tray(),
        _hotkey: shell_crates::hotkey(),
    })
}

fn request_attention(window: &ApplicationWindow) {
    #[cfg(target_os = "linux")]
    if let Some(surface) = window.surface() {
        if let Some(x11) = surface.downcast_ref::<gdk4_x11::X11Surface>() {
            #[allow(deprecated)]
            x11.set_urgency_hint(true);
            report("attention", "requested", "gdk_x11_surface_set_urgency_hint");
            return;
        }
    }
    let _ = window;
    report(
        "attention",
        "no-api",
        "GTK 4 has no attention request on this backend",
    );
}
