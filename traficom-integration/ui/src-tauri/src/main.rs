// A thin shell around the shared web UI. All authority stays on the server: this process holds no
// RF logic, no permissions and no stored token.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        // Must come first: a sign-in redirect reaches the running window, not a second copy.
        .plugin(tauri_plugin_single_instance::init(|_app, _argv, _cwd| {}))
        .plugin(tauri_plugin_deep_link::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_opener::init())
        .setup(|_app| {
            // The installer registers the scheme. An unpackaged dev build must do it itself.
            #[cfg(debug_assertions)]
            {
                use tauri_plugin_deep_link::DeepLinkExt;
                _app.deep_link().register_all()?;
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("AstraSync could not start");
}
