//! Synthetic UI only. All fixture state lives in the embedded static frontend.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("run comparison UI");
}
