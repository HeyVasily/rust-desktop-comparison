// Shared by the Rust examples' optional shell-integration checks: Cargo feature
// `shell-checks`, active only when COMPARISON_SHELL_CHECKS is set. Each check prints a
// `SHELL {json}` line; tools/shell_probe.py verifies the effect from outside the app.
#[allow(dead_code)]
mod shell_common {
    use std::io::Write;

    pub const TOOLTIP: &str = "Veranda shell check";
    pub const BADGE: i64 = 3;

    pub fn enabled() -> bool {
        std::env::var_os("COMPARISON_SHELL_CHECKS").is_some()
    }

    /// The probe minimizes the window first, so the request reaches an inactive window.
    pub fn attention_delay() -> std::time::Duration {
        let seconds = std::env::var("COMPARISON_SHELL_ATTENTION_DELAY")
            .ok()
            .and_then(|value| value.parse().ok())
            .unwrap_or(12);
        std::time::Duration::from_secs(seconds)
    }

    pub fn report(check: &str, status: &str, detail: &str) {
        let mut out = std::io::stdout().lock();
        let _ = writeln!(
            out,
            "SHELL {{\"check\":{},\"status\":{},\"detail\":{}}}",
            json(check),
            json(status),
            json(detail)
        );
        let _ = out.flush();
    }

    fn json(text: &str) -> String {
        let mut out = String::from("\"");
        for ch in text.chars() {
            match ch {
                '"' => out.push_str("\\\""),
                '\\' => out.push_str("\\\\"),
                c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
                c => out.push(c),
            }
        }
        out.push('"');
        out
    }

    /// 32×32 RGBA tray icon: blue with a white border, visible on light and dark bars.
    pub fn icon_rgba() -> (Vec<u8>, u32, u32) {
        let (width, height) = (32u32, 32u32);
        let mut pixels = Vec::with_capacity((width * height * 4) as usize);
        for y in 0..height {
            for x in 0..width {
                let edge = x < 3 || y < 3 || x >= width - 3 || y >= height - 3;
                pixels.extend_from_slice(if edge { &[255, 255, 255, 255] } else { &[42, 120, 214, 255] });
            }
        }
        (pixels, width, height)
    }
}
