// Opt-in startup observation shared by the Linux comparison examples.
use raw_window_handle::{HasDisplayHandle, RawDisplayHandle};

fn report_display<T: HasDisplayHandle>(name: &str, window: &T, width: u32, height: u32) {
    let backend = match window.display_handle().map(|handle| handle.as_raw()) {
        Ok(RawDisplayHandle::Wayland(_)) => "wayland",
        Ok(RawDisplayHandle::Xlib(_)) | Ok(RawDisplayHandle::Xcb(_)) => "x11",
        _ => "unavailable",
    };
    println!("DISPLAY_DIAGNOSTIC {{\"name\":\"{name}\",\"backend\":\"{backend}\",\"content_width\":{width},\"content_height\":{height},\"ready\":true}}");
}
