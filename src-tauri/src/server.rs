use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::{Arc, Mutex};
use std::time::Duration;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

const CREATE_NO_WINDOW: u32 = 0x0800_0000;

pub struct ServerManager {
    pub port: u16,
    pub child: Arc<Mutex<Option<Child>>>,
}

impl ServerManager {
    pub fn new() -> Self {
        // 1. 检查默认端口是否已经有运行中的 vidnote 服务
        if ping_health(18233) {
            log::info!("发现已有运行中的 vidnote 服务 (端口 18233)");
            return Self {
                port: 18233,
                child: Arc::new(Mutex::new(None)),
            };
        }

        // 2. 分配端口并启动服务
        let port = find_free_port();
        log::info!("正在为 vid2note 后端服务分配端口: {}", port);

        let child = spawn_server(port);
        let child_arc = Arc::new(Mutex::new(child));

        // 3. 等待服务就绪（最多 15 秒）
        let start = std::time::Instant::now();
        let mut ready = false;
        while start.elapsed() < Duration::from_secs(15) {
            if ping_health(port) {
                ready = true;
                break;
            }
            std::thread::sleep(Duration::from_millis(250));
        }

        if ready {
            log::info!("vid2note 后端服务已就绪: http://127.0.0.1:{}/", port);
        } else {
            log::warn!("vid2note 后端服务未在 15 秒内响应 health，继续启动前端");
        }

        // 4. 启动保活心跳线程，每 4 秒向 /api/ping 发送请求，防止后端 watchdog 退出
        let heartbeat_port = port;
        std::thread::spawn(move || loop {
            std::thread::sleep(Duration::from_secs(4));
            let _ = ping_path(heartbeat_port, "/api/ping");
        });

        Self {
            port,
            child: child_arc,
        }
    }
}

impl Drop for ServerManager {
    fn drop(&mut self) {
        if let Ok(mut lock) = self.child.lock() {
            if let Some(mut child) = lock.take() {
                log::info!("正在终止 vidnote 后端进程 (pid={})", child.id());
                let _ = child.kill();
            }
        }
    }
}

fn ping_health(port: u16) -> bool {
    ping_path(port, "/api/health")
}

fn ping_path(port: u16, path: &str) -> bool {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    if let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(600)) {
        let _ = stream.set_read_timeout(Some(Duration::from_millis(600)));
        let _ = stream.set_write_timeout(Some(Duration::from_millis(600)));
        let req = format!(
            "GET {} HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nConnection: close\r\n\r\n",
            path, port
        );
        if stream.write_all(req.as_bytes()).is_ok() {
            let mut buf = [0u8; 64];
            if let Ok(n) = stream.read(&mut buf) {
                return n > 0;
            }
        }
    }
    false
}

fn find_free_port() -> u16 {
    TcpListener::bind("127.0.0.1:0")
        .and_then(|l| l.local_addr())
        .map(|a| a.port())
        .unwrap_or(18233)
}

fn spawn_server(port: u16) -> Option<Child> {
    let mut candidates: Vec<(PathBuf, Vec<String>)> = Vec::new();

    // 候选 1：exe 旁边的 vidnote-server.exe
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            candidates.push((
                parent.join("vid2note-server.exe"),
                vec!["serve-ui".into(), "--port".into(), port.to_string()],
            ));
        }
    }

    // 候选 2：%LOCALAPPDATA%\vidnote\runtime\vidnote-server.exe
    if let Ok(local_app_data) = std::env::var("LOCALAPPDATA") {
        candidates.push((
            Path::new(&local_app_data)
                .join("vid2note")
                .join("runtime")
                .join("vid2note-server.exe"),
            vec!["serve-ui".into(), "--port".into(), port.to_string()],
        ));
    }

    // 候选 3：开发环境下的 .venv\Scripts\python.exe
    let dev_python = Path::new("..").join(".venv").join("Scripts").join("python.exe");
    candidates.push((
        dev_python,
        vec![
            "-m".into(),
            "vid2note.cli".into(),
            "serve-ui".into(),
            "--port".into(),
            port.to_string(),
        ],
    ));

    // 候选 4：系统 Python / vidnote 命令
    candidates.push((
        PathBuf::from("python"),
        vec![
            "-m".into(),
            "vid2note.cli".into(),
            "serve-ui".into(),
            "--port".into(),
            port.to_string(),
        ],
    ));

    for (bin, args) in candidates {
        if bin.exists() || bin == Path::new("python") {
            log::info!("尝试启动后端服务: {:?} {:?}", bin, args);
            let mut cmd = Command::new(&bin);
            cmd.args(&args);

            #[cfg(windows)]
            cmd.creation_flags(CREATE_NO_WINDOW);

            match cmd.spawn() {
                Ok(child) => {
                    log::info!("已启动后端子进程 (pid={})", child.id());
                    return Some(child);
                }
                Err(err) => {
                    log::debug!("尝试 {:?} 失败: {}", bin, err);
                }
            }
        }
    }

    log::error!("未找到可用的 vidnote 后端可执行文件");
    None
}
