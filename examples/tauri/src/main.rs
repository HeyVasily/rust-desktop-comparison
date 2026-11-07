//! Synthetic UI only. All fixture state lives in the embedded static frontend.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[cfg(target_os = "macos")]
use tauri::Manager;

#[cfg(target_os = "macos")]
fn log_geometry(
    window: &tauri::WebviewWindow,
    phase: &str,
) -> Result<(f64, f64), Box<dyn std::error::Error>> {
    let _main_thread = objc2::MainThreadMarker::new()
        .ok_or_else(|| std::io::Error::other("native geometry requires the main thread"))?;
    let native_pointer = window.ns_window()?.cast::<objc2_app_kit::NSWindow>();
    // SAFETY: Tauri supplies the live NSWindow for this owned window handle.
    // The main-thread check above enforces AppKit's thread requirement; this
    // shared borrow does not escape the function or take ownership of the object.
    let native = unsafe { native_pointer.as_ref() }
        .ok_or_else(|| std::io::Error::other("native comparison window missing"))?;
    let frame = native.frame();
    let layout = native.contentLayoutRect();
    let scale = window.scale_factor()?;
    let inner = window.inner_size()?;
    let outer = window.outer_size()?;
    println!(
        "geometry phase={phase} desired_visible_logical=960x640 scale_factor={scale} inner_physical={}x{} outer_physical={}x{} inner_logical={}x{} outer_logical={}x{} native_frame_logical={}x{} native_visible_content_logical={}x{}",
        inner.width,
        inner.height,
        outer.width,
        outer.height,
        f64::from(inner.width) / scale,
        f64::from(inner.height) / scale,
        f64::from(outer.width) / scale,
        f64::from(outer.height) / scale,
        frame.size.width,
        frame.size.height,
        layout.size.width,
        layout.size.height,
    );
    Ok((layout.size.width, layout.size.height))
}

fn main() {
    let builder = tauri::Builder::default();
    #[cfg(target_os = "macos")]
    let builder = builder.setup(|app| {
        let window = app
            .get_webview_window("main")
            .ok_or_else(|| std::io::Error::other("main comparison window missing"))?;
        let (visible_width, visible_height) = log_geometry(&window, "created")?;
        let observed_window = window.clone();
        window.on_window_event(move |event| {
            if matches!(event, tauri::WindowEvent::Resized(_)) {
                if let Err(error) = log_geometry(&observed_window, "resized") {
                    eprintln!("geometry read failed: {error}");
                }
            }
        });
        // With a full-size content view, Tao's inner_size includes the titlebar.
        // AppKit's contentLayoutRect measures the unobscured client area. Add
        // the measured inset to the public API size rather than assuming a
        // fixed titlebar height or repeating the ineffective configured size.
        let inner = window.inner_size()?;
        let scale = window.scale_factor()?;
        let width = 960.0 + (f64::from(inner.width) / scale - visible_width).max(0.0);
        let height = 640.0 + (f64::from(inner.height) / scale - visible_height).max(0.0);
        println!("geometry requested_tauri_inner_logical={width}x{height}");
        window.set_size(tauri::LogicalSize::new(width, height))?;
        Ok(())
    });
    builder
        .run(tauri::generate_context!())
        .expect("run comparison UI");
}
