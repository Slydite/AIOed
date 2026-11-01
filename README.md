# AIOed — DeepCool LM360 Display Manager

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-blue)](https://github.com/Slydite/AIOed)
[![Python](https://img.shields.io/badge/python-3.10+-brightgreen.svg)](https://www.python.org/)

An ultra-lightweight, high-performance background service and responsive web dashboard for the **DeepCool LM360** (and LM-series) AIO liquid cooler LCD screen.

Designed from the ground up to replace heavy proprietary software with a fast, modular Python daemon consuming **~5 MB RAM** and virtually **0% CPU**.

---

## ✨ Features

- **🚀 Ultra-Low Resource Usage**: Direct native WinUSB bulk pipe communication (`0xAA 0x01` protocol) with pre-baked RGB565 streaming. Consumes ~5 MB RAM and 0.00% CPU in media loop mode.
- **🔄 Hardware Inverted Orientation (180°)**: Enabled by default since LM-series coolers are typically mounted upside-down. Frames are pre-rendered inverted for zero runtime rotation overhead.
- **📊 Live Hardware Monitor Mode**:
  - **`cyber_stats` (Default)**: High-contrast, large-font HUD displaying CPU, GPU, and RAM stats with dynamic value-based color shifting (Cyan ➔ Green ➔ Yellow ➔ Orange ➔ Red) and breathing luminous neon accents.
  - **`cyber_dual`**: Futuristic dual-card layout with live clock and dynamic accent bars.
  - **`white_edition`**: Minimal frosty theme designed specifically for the LM360 White edition cooler.
  - **`single_gauge`**: Hero gauge ring with secondary telemetry badges.
  - **`retro_matrix`**: Monospace green phosphor terminal HUD with ASCII telemetry bars.
- **🔤 Interactive Text Animation Studio**:
  - Multi-element layout with independent text, fonts, font sizes, colors, and glow accents.
  - Full **2D interactive drag-and-drop** on a 1:1 scale 320×240 preview stage.
  - Real-time telemetry tags (`{time}`, `{date}`, `{cpu_temp}`, `{gpu_temp}`, `{cpu_load}`, `{gpu_load}`, `{cpu_power}`, `{gpu_power}`, `{ram_load}`, `{cpu_clock}`).
  - Built-in visual effects: Neon Pulse, Marquee Ticker, RGB Rainbow Wave, Matrix Rain, Cyber Glitch, Typewriter, Sine Wave, and Static.
  - One-click **"Save as Looping Video"** to export animations into the zero-CPU Media Library.
- **🎞️ Zero-CPU Media Library**:
  - Import any GIF, MP4, WEBM, PNG, or JPG.
  - Smart 4:3 center crop, scale, and trim modal with instant pre-rendering to raw RGB565 binary loops.
  - Zero-CPU playback directly from disk DMA to USB.
  - Custom media storage folder selection with automatic file migration.
- **☀️ Display Brightness Control**: Smooth linear software dimming from 10% to 100% (safe bulk packet scaling with zero panel register corruption).
- **📡 Native Sensor Bridge**: Connects directly to DeepCool's low-overhead named pipe (`\\.\pipe\jzfs_sensor_bridge_v2`) for kernel-level CPU/GPU temperatures, powers, clock frequencies, and memory usage. Falls back seamlessly to `psutil`.
- **🌐 Responsive Web Dashboard**: Dark-mode web interface at `http://localhost:5220` with a zero-lag 25 FPS live MJPEG stream mirror of the cooler screen.
- **🖥️ System Tray Integration**: Minimizes quietly to the Windows system tray with quick mode switching, orientation toggle, brightness presets, and dashboard launcher.

---

## ⚡ Quick 1-Click Installation

1. **Clone or Download this repository:**
   ```bash
   git clone https://github.com/Slydite/AIOed.git
   cd AIOed
   ```

2. **Run `install.bat`**:
   - Double-click **`install.bat`**.
   - It will automatically set up the Python virtual environment, install requirements, and create the **"AIOed Dashboard"** desktop shortcut.
   - It will also offer to enable automatic Windows startup (silent background service).

That's it!

---

## 🚀 Usage & Controls

### 🖥️ Open Dashboard Anytime
- **Desktop Icon:** Double-click the **AIOed Dashboard** icon on your Desktop. If the service isn't running yet, it starts it silently in the background and opens the dashboard in your default browser!
- **Browser:** Navigate to **[http://localhost:5220](http://localhost:5220)**.
- **System Tray:** Double-click the AIOed tray icon in your Windows notification area.

### 🛡️ Running as a Silent Background Service
- Double-click **`run_background.vbs`** (or `run_background.bat`).
- The controller will run invisibly with zero command prompt windows, quietly sitting in the Windows notification tray.

### 🛑 Stopping the Service
- **From Tray:** Right-click the AIOed system tray icon and click **Exit**.
- **From Folder:** Double-click **`stop_service.bat`**.

### 🔁 Windows Startup (Autostart)
- Toggle **Run at Startup** directly in the Web Dashboard, or during `install.bat`.
- Starts silently on login via `wscript.exe` with no terminal flashing.

---

## 🗂️ Project Structure

```text
AIOed/
├── assets/
│   └── fonts/                 # Bundled typography (Orbitron, Press Start 2P, etc.)
├── deepcool_lm/
│   ├── __init__.py
│   ├── config.py              # Settings manager & registry autostart
│   ├── media_manager.py       # GIF/MP4 processor, crop/trim, RGB565 streamer
│   ├── sensor_bridge.py       # Named pipe client for hardware sensor bridge
│   ├── server.py              # FastAPI web server & live preview streamer
│   ├── service.py             # Display pipeline orchestrator & background thread
│   ├── text_animator.py       # Multi-element text animation & loop baking engine
│   ├── tray.py                # Windows system tray menu
│   ├── usb_driver.py          # Native WinUSB bulk pipe interface
│   └── themes/                # Monitor HUD theme implementations
│       ├── __init__.py
│       ├── theme_base.py      # Abstract base theme class & metric formatting
│       ├── theme_registry.py  # Theme loader & registry
│       ├── cyber_stats.py     # Default high-contrast large-font HUD
│       ├── cyber_dual.py      # Dual-card HUD with live clock
│       ├── white_edition.py   # Minimal frosty theme
│       ├── single_gauge.py    # Circular hero gauge HUD
│       └── retro_matrix.py    # Terminal phosphor ASCII HUD
├── web/
│   └── index.html             # Responsive HTML5/CSS3 dashboard with live stage
├── install.bat                # 1-click automatic setup and shortcut generator
├── uninstall.bat              # Stop service, remove autostart & shortcuts
├── run.bat                    # Launch in foreground console mode
├── run_background.bat         # Launch silently via VBS wrapper
├── run_background.vbs         # Silent background runner
├── open_dashboard.vbs         # Instant dashboard launcher with auto-start daemon
├── create_shortcuts.vbs       # Creates Desktop & Start Menu shortcuts
├── stop_service.bat           # Safely stops running instances
├── config.example.json        # Template configuration
├── requirements.txt           # Python dependencies
├── icon.ico                   # Application icon
└── README.md
```

---

## ⚙️ Configuration (`config.json`)

The configuration file is automatically created on first launch with sensible defaults:

```json
{
  "mode": "monitor",
  "orientation": 180,
  "active_theme": "cyber_stats",
  "temp_unit": "C",
  "brightness": 100,
  "playback_fps_cap": 30,
  "web_port": 5220,
  "autostart": false,
  "media_storage_dir": "media_store"
}
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
