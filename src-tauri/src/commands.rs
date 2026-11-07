use crate::server::ServerManager;
use serde::Serialize;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::sync::Arc;
use std::time::Duration;
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
        name: "vid2note".into(),
        version: "0.4.6".into(),
        platform: std::env::consts::OS.into(),
        tauri: true,
    }
}

/// 原生直接代理本地 API，完全避免 WebView2 跨域 (CORS) 和 OPTIONS 预检失败
#[tauri::command]
pub fn tauri_api(
    server: State<Arc<ServerManager>>,
    path: String,
    method: Option<String>,
    body: Option<String>,
) -> Result<String, String> {
    let port = server.port;
    let m = method.unwrap_or_else(|| "GET".into()).to_uppercase();
    let b = body.unwrap_or_default();
    let b_bytes = b.as_bytes();

    let addr = SocketAddr::from(([127, 0, 0, 1], port));

    // 如果服务仍在冷启动解压，自动重试最多 3 秒
    let mut stream = None;
    for _ in 0..10 {
        if let Ok(s) = TcpStream::connect_timeout(&addr, Duration::from_millis(800)) {
            stream = Some(s);
            break;
        }
        std::thread::sleep(Duration::from_millis(300));
    }

    let mut stream = stream.ok_or_else(|| {
        format!(
            "无法连接后端服务 (127.0.0.1:{}): 后端正在初始化中，请稍候重试",
            port
        )
    })?;

    stream
        .set_read_timeout(Some(Duration::from_secs(180)))
        .map_err(|e| e.to_string())?;
    stream
        .set_write_timeout(Some(Duration::from_secs(10)))
        .map_err(|e| e.to_string())?;

    let req = format!(
        "{} {} HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        m,
        path,
        port,
        b_bytes.len()
    );

    stream
        .write_all(req.as_bytes())
        .map_err(|e| format!("发送请求头失败: {}", e))?;
    if !b_bytes.is_empty() {
        stream
            .write_all(b_bytes)
            .map_err(|e| format!("发送请求体失败: {}", e))?;
    }

    let mut response_bytes = Vec::new();
    stream
        .read_to_end(&mut response_bytes)
        .map_err(|e| format!("读取后端响应失败: {}", e))?;

    let response_str = String::from_utf8_lossy(&response_bytes);
    if let Some(pos) = response_str.find("\r\n\r\n") {
        let body_str = &response_str[pos + 4..];
        Ok(body_str.to_string())
    } else {
        Ok(response_str.to_string())
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
                .arg(format!("/select,{}", win_path))
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
pub fn open_folder(path: String) -> Result<(), String> {
    let p = std::path::Path::new(&path);
    let target = if p.is_file() {
        p.parent().unwrap_or(p)
    } else {
        p
    };
    if !target.exists() {
        return Err(format!("目录不存在: {}", target.display()));
    }

    #[cfg(windows)]
    {
        let win_path = target.to_string_lossy().replace('/', "\\");
        std::process::Command::new("explorer")
            .arg(&win_path)
            .spawn()
            .map_err(|e| format!("无法打开目录: {}", e))?;
        Ok(())
    }

    #[cfg(not(windows))]
    {
        open::that(target).map_err(|e| format!("无法打开目录: {}", e))
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

#[tauri::command]
pub fn minimize_window(window: WebviewWindow) -> Result<(), String> {
    window.minimize().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn toggle_maximize_window(window: WebviewWindow) -> Result<bool, String> {
    let is_max = window.is_maximized().map_err(|e| e.to_string())?;
    if is_max {
        window.unmaximize().map_err(|e| e.to_string())?;
        Ok(false)
    } else {
        window.maximize().map_err(|e| e.to_string())?;
        Ok(true)
    }
}

#[tauri::command]
pub fn is_window_maximized(window: WebviewWindow) -> Result<bool, String> {
    window.is_maximized().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn close_window(window: WebviewWindow) -> Result<(), String> {
    window.hide().map_err(|e| e.to_string())
}
