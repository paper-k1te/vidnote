use crate::server::ServerManager;
use serde::Serialize;
use std::sync::Arc;
use tauri::{State, WebviewWindow};

#[derive(Serialize)]
pub struct AppInfo {
    pub name: String,
    pub version: String,
    pub platform: String,
    pub tauri: bool,
}

#[tauri::command]
pub fn get_server_port(server: State<Arc<ServerManager>>) -> u16 {
    server.port
}

#[tauri::command]
pub fn get_app_info() -> AppInfo {
    AppInfo {
        name: "vidnote".into(),
        version: "0.3.4".into(),
        platform: std::env::consts::OS.into(),
        tauri: true,
    }
}

#[tauri::command]
pub fn pick_folder() -> Option<String> {
    rfd::FileDialog::new()
        .set_title("选择笔记保存目录")
        .pick_folder()
        .map(|p| p.to_string_lossy().to_string())
}

#[tauri::command]
pub fn reveal_path(path: String) -> Result<(), String> {
    let p = std::path::Path::new(&path);
    if !p.exists() {
        return Err(format!("路径不存在: {}", path));
    }

    #[cfg(windows)]
    {
        let win_path = path.replace('/', "\\");
        if p.is_file() {
            std::process::Command::new("explorer")
                .arg(format!("/select,\"{}\"", win_path))
                .spawn()
                .map_err(|e| format!("无法在文件管理器中定位: {}", e))?;
        } else {
            std::process::Command::new("explorer")
                .arg(&win_path)
                .spawn()
                .map_err(|e| format!("无法打开目录: {}", e))?;
        }
        Ok(())
    }

    #[cfg(not(windows))]
    {
        open::that(&path).map_err(|e| format!("无法打开: {}", e))
    }
}

#[tauri::command]
pub fn open_file(path: String) -> Result<(), String> {
    open::that(&path).map_err(|e| format!("无法打开文件: {}", e))
}

#[tauri::command]
pub fn open_external_url(url: String) -> Result<(), String> {
    open::that(&url).map_err(|e| format!("无法在浏览器中打开链接: {}", e))
}

#[tauri::command]
pub fn hide_to_tray(window: WebviewWindow) -> Result<(), String> {
    window.hide().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn show_window(window: WebviewWindow) -> Result<(), String> {
    window.show().map_err(|e| e.to_string())?;
    window.unminimize().map_err(|e| e.to_string())?;
    window.set_focus().map_err(|e| e.to_string())?;
    Ok(())
}
