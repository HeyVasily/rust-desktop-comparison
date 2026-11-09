// Crate-based shell checks for examples whose framework has no built-in API:
// global-hotkey (Ctrl+Alt+Shift+F9) and single-instance.
#[allow(dead_code)]
mod shell_crates {
    use super::shell_common::report;

    /// Exits a second launch; keep the returned guard alive in the first one.
    pub fn single_instance(name: &str) -> Option<single_instance::SingleInstance> {
        // Linux: abstract socket, Windows: named mutex, macOS: lock on a file path.
        let key = if cfg!(target_os = "macos") {
            std::env::temp_dir().join(format!("{name}.lock")).to_string_lossy().into_owned()
        } else {
            name.to_owned()
        };
        match single_instance::SingleInstance::new(&key) {
            Ok(guard) if guard.is_single() => {
                report("single-instance", "primary", "single-instance crate");
                Some(guard)
            }
            Ok(_) => {
                report("single-instance", "second-exits", "another instance holds the lock");
                std::process::exit(0)
            }
            Err(error) => {
                report("single-instance", "error", &error.to_string());
                None
            }
        }
    }

    /// Create on the thread that runs the event loop (the main thread on macOS).
    pub fn hotkey() -> Option<global_hotkey::GlobalHotKeyManager> {
        use global_hotkey::hotkey::{Code, HotKey, Modifiers};
        use global_hotkey::{GlobalHotKeyEvent, GlobalHotKeyManager, HotKeyState};
        let manager = match GlobalHotKeyManager::new() {
            Ok(manager) => manager,
            Err(error) => {
                report("hotkey", "error", &error.to_string());
                return None;
            }
        };
        GlobalHotKeyEvent::set_event_handler(Some(|event: GlobalHotKeyEvent| {
            if event.state == HotKeyState::Pressed {
                report("hotkey", "event", "Ctrl+Alt+Shift+F9 pressed");
            }
        }));
        let key = HotKey::new(Some(Modifiers::CONTROL | Modifiers::ALT | Modifiers::SHIFT), Code::F9);
        match manager.register(key) {
            Ok(()) => report("hotkey", "registered", "global-hotkey crate"),
            Err(error) => report("hotkey", "error", &error.to_string()),
        }
        Some(manager)
    }
}
