![PC Health Monitor](https://img.shields.io/badge/PC%20Health%20Monitor-Silicon%20to%20Display-8f7fe0?style=for-the-badge&labelColor=171129)

> **Streaming 7 live system metrics — from silicon registers to a physical I²C display — with zero dashboard, zero latency, zero overhead.**

---

![Python](https://img.shields.io/badge/Python-3.x-8f7fe0?style=flat-square&logo=python&logoColor=white&labelColor=171129)
![Arduino](https://img.shields.io/badge/Arduino-Nano-8f7fe0?style=flat-square&logo=arduino&logoColor=white&labelColor=171129)
![psutil](https://img.shields.io/badge/psutil-Telemetry%20Engine-8f7fe0?style=flat-square&labelColor=171129)
![PySerial](https://img.shields.io/badge/PySerial-UART%20Bridge-8f7fe0?style=flat-square&labelColor=171129)
![GPU-Z](https://img.shields.io/badge/GPU--Z-Sensor%20Backend-8f7fe0?style=flat-square&labelColor=171129)
![I2C](https://img.shields.io/badge/I²C-LCD%20Display-8f7fe0?style=flat-square&labelColor=171129)
![Windows](https://img.shields.io/badge/Windows-10%2F11-8f7fe0?style=flat-square&logo=windows&logoColor=white&labelColor=171129)

---

## Executive Summary

Most developers monitor their PC through software dashboards — a floating widget, a browser tab, something that competes for screen space. This system puts live metrics on dedicated physical hardware: a 24×4 I²C LCD that is always visible, always updated, and requires zero interaction. Plug in the USB drive, run the binary, and within 10 seconds your CPU load, GPU temperature, RAM usage, disk I/O activity, and power draw are rendering on a real display — sourced directly from your silicon.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  WINDOWS HOST                                               │
│                                                             │
│  ┌──────────────┐      ┌──────────────────────────────────┐ │
│  │   GPU-Z      │─────▶│   PCHealthMonitor.py             │ │
│  │  gpu_log.txt │      │                                  │ │
│  │  (CSV tail)  │      │  ├─ psutil → CPU / RAM / Disk   │ │
│  └──────────────┘      │  ├─ GPU-Z log parser → GPU data │ │
│                        │  └─ Serial TX  @  9600 baud     │ │
│  ┌──────────────┐      └──────────────┬───────────────────┘ │
│  │   psutil     │─────▶               │                     │
│  │  CPU·RAM·    │      USB · CH340 · CDC-ACM               │
│  │  Disk I/O    │                     │                     │
│  └──────────────┘      ┌──────────────▼───────────────────┐ │
│                        │   Arduino Nano  (ATmega328P)     │ │
└────────────────────────│   Serial RX → Key-prefix parser  │─┘
                         │   I²C Master  ·  A4 SDA · A5 SCL│
                         └──────────────┬───────────────────┘
                                        │  I²C @ 0x27
                         ┌──────────────▼───────────────────┐
                         │       24×4 I²C LCD               │
                         │  CPU: XX%      GPU: XX%          │
                         │  DISK: XX%     RAM: XX%          │
                         │  cTEMP: XX°C   gTEMP: XX°C       │
                         │  gPWR: XXXW                      │
                         └──────────────────────────────────┘
```

---

## Engineering Deep Dive — Multi-Source Sensor Fusion

### The Problem: GPU metrics are locked on Windows

`psutil` gives you CPU, RAM, and disk — but GPU load, temperature, and power draw sit behind proprietary NVIDIA/AMD driver interfaces. A kernel driver or licensed SDK would work, but neither is portable or dependency-light.

### The Solution: GPU-Z as a headless sensor backend

GPU-Z has a CSV logging mode. I automated its launch at startup, minimized its window programmatically via `pygetwindow`, and built a file-tail parser that reads the last line of `gpu_log.txt` on every polling cycle:

```python
def get_gpu_metrics_from_log(log_file_path):
    with open(log_file_path, 'r') as f:
        lines = f.readlines()
        if lines:
            last_line = lines[-1]
            parts = last_line.split(",")
            if len(parts) > 4:
                gpu_temp  = min(round(float(parts[1].strip())), 99)
                gpu_load  = min(round(float(parts[2].strip())), 99)
                gpu_power = min(round(float(parts[3].strip())), 999)
                cpu_temp  = min(round(float(parts[4].strip())), 99)
                return (f"gTEMP:{gpu_temp} GPU:{gpu_load}% "
                        f"gPWR:{gpu_power}W cTEMP:{cpu_temp}")
```

The `len(parts) > 4` guard silently skips partial writes — GPU-Z flushes new rows while Python is reading, and this prevents any corrupt data from reaching the display.

---

### The UART Protocol: fitting 7 metrics into one packet

The Arduino has 2KB of SRAM, no heap allocator, and no JSON parser. Every metric needed to fit in a single `Serial.readStringUntil('\n')` call with deterministic, zero-allocation field extraction.

**The packet format:**
```
CPU:42% RAM:67% DISK:12% gTEMP:57 GPU:23% gPWR:85W cTEMP:57
```

**The Arduino parser — O(n), no dynamic memory:**
```cpp
int cpuIndex = data.indexOf("CPU:");
String cpuUsage = data.substring(cpuIndex + 4, ramIndex - 1);
// Repeat for every field
```

`data.indexOf()` + `data.substring()` extracts every field in a single pass with no heap allocation. Designed for a microcontroller with 2KB of SRAM — built to never crash.

---

### Disk I/O: why percentage alone is wrong

`psutil.disk_usage()` returns storage capacity (GB used/free) — useless for a health monitor. What matters is *activity*. I built a delta sampler that diffs read/write operation counts over a 1-second window:

```python
def calculate_disk_io_utilization(interval=1.0):
    io_start = psutil.disk_io_counters()
    time.sleep(interval)
    io_end   = psutil.disk_io_counters()
    ops = (io_end.read_count  - io_start.read_count) + \
          (io_end.write_count - io_start.write_count)
    return min(99, max(0, round((ops / (interval * 100)) * 100)))
```

This gives a true I/O activity percentage that spikes when your disk is actually working — not a static capacity reading.

---

## Hardware

| Component | Spec | Role |
|---|---|---|
| Arduino Nano | ATmega328P · 16MHz · 2KB SRAM | Serial RX + I²C master |
| 24×4 I²C LCD | PCF8574 backpack · addr 0x27 | Live metric display |
| USB cable | Standard USB-A · CH340 chip | Power + UART bridge |
| Breadboard | Standard 400-tie | Prototyping chassis |

**Wiring — Arduino Nano to LCD:**

| Arduino Pin | LCD Pin |
|---|---|
| A4 | SDA |
| A5 | SCL |
| 5V | VCC |
| GND | GND |

---

## What Gets Displayed

| LCD Row | Left | Right |
|---|---|---|
| Row 0 | `CPU: XX%` | `GPU: XX%` |
| Row 1 | `DISK: XX%` | `RAM: XX%` |
| Row 2 | `cTEMP: XX°C` | `gTEMP: XX°C` |
| Row 3 | `gPWR: XXXW` | — |

---

## Installation & Usage

### Prerequisites
- Windows 10 or 11
- Python 3.8+
- Arduino IDE (for flashing firmware)
- CH340 USB driver (usually auto-installed by Windows)

### Step 1 — Flash the Arduino firmware

1. Open `arduino_code/arduino_code.ino` in Arduino IDE
2. Go to **Tools → Board → Arduino Nano**
3. Select the correct COM port under **Tools → Port**
4. Click **Upload**

### Step 2 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### Step 3 — Run

Place `GPU-Z.exe` in the same directory as `PCHealthMonitor.py`, then:

```bash
python PCHealthMonitor.py
```

The script will:
- Launch and auto-minimize GPU-Z
- Wait for the GPU log to initialize (~5 seconds)
- Auto-detect the Arduino COM port
- Begin streaming all 7 metrics to the LCD at 1-second intervals
- Add itself to Windows Startup automatically
- Create a system tray icon — right-click to exit

### Step 4 — Packaged deployment (optional)

For a plug-and-play USB deployment, place the compiled `PCHealthMonitor.exe` alongside `GPU-Z.exe` and `usbicon.ico` on a USB drive. Run as Administrator. The app handles startup registration automatically.

---

## Project Context

Built in late 2024 as an exploration of hardware-software co-design on constrained embedded systems. The goal: a portable, no-install monitoring solution that works on any Windows machine — plug in the USB, metrics appear on physical hardware within 10 seconds.

Published in 2025 as part of documenting my systems engineering portfolio.

---

## Contact

**Roshaan Ahsan** — Product Engineer

[![Email](https://img.shields.io/badge/Email-roshaanahsan.pro%40gmail.com-8f7fe0?style=flat-square&labelColor=171129)](mailto:roshaanahsan.pro@gmail.com)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-roshaanahsan-8f7fe0?style=flat-square&logo=linkedin&logoColor=white&labelColor=171129)](https://linkedin.com/in/roshaanahsan)
[![GitHub](https://img.shields.io/badge/GitHub-roshaanahsan-8f7fe0?style=flat-square&logo=github&logoColor=white&labelColor=171129)](https://github.com/roshaanahsan)
[![X](https://img.shields.io/badge/X-roshaanahsan-8f7fe0?style=flat-square&logo=x&logoColor=white&labelColor=171129)](https://x.com/roshaanahsan)
