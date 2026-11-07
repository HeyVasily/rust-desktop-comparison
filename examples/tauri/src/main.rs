//! Synthetic UI only. All fixture state lives in the embedded static frontend.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;

fn log_geometry(window: &tauri::WebviewWindow, phase: &str) -> tauri::Result<()> {
    let scale = window.scale_factor()?;
    let inner = window.inner_size()?;
    let outer = window.outer_size()?;
    println!(
        "geometry phase={phase} configured_inner_logical=960x640 scale_factor={scale} inner_physical={}x{} outer_physical={}x{} inner_logical={}x{} outer_logical={}x{}",
        inner.width,
        inner.height,
        outer.width,
        outer.height,
        f64::from(inner.width) / scale,
        f64::from(inner.height) / scale,
        f64::from(outer.width) / scale,
        f64::from(outer.height) / scale,
    );
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let window = app
                .get_webview_window("main")
                .ok_or_else(|| std::io::Error::other("main comparison window missing"))?;
            log_geometry(&window, "created")?;
            let observed_window = window.clone();
            window.on_window_event(move |event| {
                if matches!(event, tauri::WindowEvent::Resized(_)) {
                    if let Err(error) = log_geometry(&observed_window, "resized") {
                        eprintln!("geometry read failed: {error}");
                    }
                }
            });
            // Tao 0.37.2 routes this public API to NSWindow.setContentSize,
            // asynchronously. The resize event above records the applied size.
            // The creation path on the hosted macOS runner included its titlebar
            // in the configured height, leaving only 612 points of client area.
            #[cfg(target_os = "macos")]
            window.set_size(tauri::LogicalSize::new(960.0, 640.0))?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("run comparison UI");
}
