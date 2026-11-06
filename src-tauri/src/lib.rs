pub mod commands;
pub mod server;
pub mod tray;

use commands::*;
use server::ServerManager;
use std::sync::Arc;
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let server_manager = Arc::new(ServerManager::new());

    tauri::Builder::default()
        .manage(server_manager)
        .setup(|app| {
            // 设置系统托盘核心
            if let Err(e) = tray::setup_tray(app.handle()) {
                log::error!("初始化系统托盘失败: {}", e);
            }

            // 拦截主窗口关闭事件，点击关闭按钮时隐藏到托盘而不是直接杀死应用
            if let Some(window) = app.get_webview_window("main") {
                let w = window.clone();
                window.on_window_event(move |event| {
                    if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                        let _ = w.hide();
                    }
                });
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_server_port,
            get_app_info,
            tauri_api,
            pick_folder,
            reveal_path,
            open_folder,
            open_file,
            open_external_url,
            hide_to_tray,
            show_window
        ])
        .run(tauri::generate_context!())
        .expect("error while running vidnote application");
}
