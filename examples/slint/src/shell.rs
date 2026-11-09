//! Optional shell-integration checks (feature `shell-checks`, env COMPARISON_SHELL_CHECKS).
//! The tray uses Slint's built-in SystemTrayIcon; attention goes through winit.
include!("../../shell_common.rs");
include!("../../shell_crates.rs");

use shell_common::report;
use slint::ComponentHandle;

slint::slint! {
    export component ShellTray inherits SystemTrayIcon {
        in property <image> tray-image;
        callback tray-clicked();
        callback menu-chosen(string);
        icon: tray-image;
        tooltip: "Veranda shell check";
        clicked => { root.tray-clicked(); }
        Menu {
            MenuItem { title: "Show window"; activated => { root.menu-chosen("show"); } }
            MenuItem { title: "Quit"; activated => { root.menu-chosen("quit"); } }
        }
    }
}

pub struct Shell {
    _tray: Option<ShellTray>,
    _hotkey: Option<global_hotkey::GlobalHotKeyManager>,
}

pub fn single_instance() -> Option<single_instance::SingleInstance> {
    shell_common::enabled()
        .then(|| shell_crates::single_instance("veranda-shell-slint"))
        .flatten()
}

pub fn start(window: &slint::Weak<super::Demo>) -> Option<Shell> {
    if !shell_common::enabled() {
        return None;
    }
    report("badge", "no-api", "Slint has no Dock or taskbar badge API");
    let weak = window.clone();
    slint::Timer::single_shot(shell_common::attention_delay(), move || {
        use slint::winit_030::{WinitWindowAccessor, winit::window::UserAttentionType};
        let Some(ui) = weak.upgrade() else { return };
        let done = ui.window().with_winit_window(|window| {
            window.request_user_attention(Some(UserAttentionType::Critical));
        });
        match done {
            Some(()) => report(
                "attention",
                "requested",
                "winit request_user_attention via WinitWindowAccessor",
            ),
            None => report("attention", "error", "no winit window"),
        }
    });
    Some(Shell {
        _tray: tray(),
        _hotkey: shell_crates::hotkey(),
    })
}

fn tray() -> Option<ShellTray> {
    let tray = match ShellTray::new() {
        Ok(tray) => tray,
        Err(error) => {
            report("tray", "error", &error.to_string());
            return None;
        }
    };
    let (rgba, width, height) = shell_common::icon_rgba();
    let buffer =
        slint::SharedPixelBuffer::<slint::Rgba8Pixel>::clone_from_slice(&rgba, width, height);
    tray.set_tray_image(slint::Image::from_rgba8(buffer));
    tray.on_tray_clicked(|| report("tray", "click", "SystemTrayIcon clicked()"));
    tray.on_menu_chosen(|id| report("tray", "menu", &id));
    match tray.show() {
        Ok(()) => {
            report("tray", "created", "Slint SystemTrayIcon");
            Some(tray)
        }
        Err(error) => {
            report("tray", "error", &error.to_string());
            None
        }
    }
}
