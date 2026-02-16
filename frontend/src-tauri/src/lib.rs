use std::env;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::mpsc;
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

struct SidecarState {
    child: Mutex<Option<Child>>,
    port: Mutex<u16>,
}

fn find_project_root() -> PathBuf {
    let mut dir = env::current_dir().expect("Failed to get current dir");
    loop {
        if dir.join("pyproject.toml").exists() {
            return dir;
        }
        if !dir.pop() {
            panic!("Could not find project root (pyproject.toml)");
        }
    }
}

fn spawn_sidecar(app_handle: &tauri::AppHandle) -> (Child, u16) {
    let mut child = if cfg!(debug_assertions) {
        // Dev mode: spawn via uv run -m app
        let project_root = find_project_root();
        Command::new("uv")
            .args(["run", "-m", "app"])
            .env("PYTHONPATH", project_root.join("src"))
            .current_dir(&project_root)
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .expect("Failed to spawn sidecar — is `uv` installed?")
    } else {
        // Production mode: spawn bundled sidecar binary
        let resource_dir = app_handle
            .path()
            .resource_dir()
            .expect("Failed to get resource directory");
        let sidecar_path = resource_dir.join("sidecar").join("nomen-sidecar.exe");

        if !sidecar_path.exists() {
            panic!("Sidecar binary not found at {:?}", sidecar_path);
        }

        Command::new(&sidecar_path)
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .expect("Failed to spawn sidecar binary")
    };

    let stdout = child.stdout.take().expect("Failed to capture sidecar stdout");

    let (tx, rx) = mpsc::channel();
    std::thread::spawn(move || {
        let reader = BufReader::new(stdout);
        let mut port_sent = false;
        for line in reader.lines() {
            let Ok(line) = line else { break };
            if !port_sent {
                if let Some(port_str) = line.strip_prefix("PORT=") {
                    let port: u16 = port_str.parse().expect("Sidecar printed invalid port");
                    let _ = tx.send(port);
                    port_sent = true;
                }
            }
            // Keep draining stdout so the pipe buffer never fills.
            // (PyTorch on Windows blocks if the pipe read-end closes.)
        }
    });

    let port = rx
        .recv_timeout(Duration::from_secs(30))
        .expect("Sidecar did not report port within 30s");

    (child, port)
}

fn kill_process_tree(child: &mut Child) {
    let pid = child.id();
    let _ = Command::new("taskkill")
        .args(["/F", "/T", "/PID", &pid.to_string()])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();
}

#[tauri::command]
fn get_sidecar_port(state: tauri::State<SidecarState>) -> Result<u16, String> {
    let port = *state.port.lock().map_err(|e| e.to_string())?;
    if port == 0 {
        Err("Sidecar port not available".to_string())
    } else {
        Ok(port)
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(SidecarState {
            child: Mutex::new(None),
            port: Mutex::new(0),
        })
        .invoke_handler(tauri::generate_handler![get_sidecar_port])
        .setup(|app| {
            let (child, port) = spawn_sidecar(app.handle());

            let state = app.state::<SidecarState>();
            *state.child.lock().unwrap() = Some(child);
            *state.port.lock().unwrap() = port;

            app.handle().plugin(tauri_plugin_dialog::init())?;
            app.handle().plugin(tauri_plugin_http::init())?;

            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
                app.handle().plugin(
                    tauri_plugin_mcp::init_with_config(
                        tauri_plugin_mcp::PluginConfig::new("NomenAudio".to_string())
                            .start_socket_server(true)
                            .tcp("127.0.0.1".to_string(), 9876),
                    ),
                )?;
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let state = window.state::<SidecarState>();
                let mut guard = state.child.lock().unwrap();
                if let Some(ref mut child) = *guard {
                    kill_process_tree(child);
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
