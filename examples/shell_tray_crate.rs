// Tray icon through the tray-icon crate, for examples without a built-in tray
// (egui, GTK 4). On Linux the ksni backend talks StatusNotifierItem over D-Bus,
// without GTK 3, so it also works inside a GTK 4 process.
#[allow(dead_code)]
mod shell_tray_crate {
    use super::shell_common::{icon_rgba, report, TOOLTIP};

    /// Create after the event loop has started (macOS needs a running NSApplication).
    pub fn tray() -> Option<tray_icon::TrayIcon> {
        use tray_icon::menu::{Menu, MenuEvent, MenuItem};
        use tray_icon::{Icon, MouseButtonState, TrayIconBuilder, TrayIconEvent};
        let menu = Menu::new();
        let show = MenuItem::with_id("show", "Show window", true, None);
        let quit = MenuItem::with_id("quit", "Quit", true, None);
        if let Err(error) = menu.append_items(&[&show, &quit]) {
            report("tray", "error", &error.to_string());
        }
        TrayIconEvent::set_event_handler(Some(|event: TrayIconEvent| match event {
            TrayIconEvent::Click { button, button_state: MouseButtonState::Up, .. } => {
                report("tray", "click", &format!("{button:?}"))
            }
            TrayIconEvent::DoubleClick { button, .. } => report("tray", "click", &format!("double {button:?}")),
            _ => {}
        }));
        MenuEvent::set_event_handler(Some(|event: MenuEvent| report("tray", "menu", &event.id.0)));
        let (rgba, width, height) = icon_rgba();
        let icon = match Icon::from_rgba(rgba, width, height) {
            Ok(icon) => icon,
            Err(error) => {
                report("tray", "error", &error.to_string());
                return None;
            }
        };
        match TrayIconBuilder::new()
            .with_menu(Box::new(menu))
            .with_tooltip(TOOLTIP)
            .with_icon(icon)
            .build()
        {
            Ok(tray) => {
                report("tray", "created", "tray-icon crate");
                Some(tray)
            }
            Err(error) => {
                report("tray", "error", &error.to_string());
                None
            }
        }
    }
}
