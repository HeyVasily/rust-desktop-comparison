//! Optional shell-integration checks (feature `shell-checks`, env COMPARISON_SHELL_CHECKS).
include!("../../shell_common.rs");
include!("../../shell_crates.rs");
include!("../../shell_tray_crate.rs");

use eframe::egui::{Context, UserAttentionType, ViewportCommand};
use shell_common::report;

pub struct Shell {
    _tray: Option<tray_icon::TrayIcon>,
    _hotkey: Option<global_hotkey::GlobalHotKeyManager>,
}

pub fn single_instance() -> Option<single_instance::SingleInstance> {
    shell_common::enabled()
        .then(|| shell_crates::single_instance("veranda-shell-egui"))
        .flatten()
}

/// Called from eframe's creation callback, on the running main event loop.
pub fn start(ctx: &Context) -> Option<Shell> {
    if !shell_common::enabled() {
        return None;
    }
    report("badge", "no-api", "eframe has no Dock or taskbar badge API");
    let ctx = ctx.clone();
    std::thread::spawn(move || {
        std::thread::sleep(shell_common::attention_delay());
        ctx.send_viewport_cmd(ViewportCommand::RequestUserAttention(
            UserAttentionType::Critical,
        ));
        ctx.request_repaint();
        report(
            "attention",
            "requested",
            "ViewportCommand::RequestUserAttention",
        );
    });
    Some(Shell {
        _tray: shell_tray_crate::tray(),
        _hotkey: shell_crates::hotkey(),
    })
}
