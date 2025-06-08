<div align="center">
  <img src="https://github.com/Sparkplugx1904/NetBench/blob/main/NetBS.png" alt="NetBS Logo" width="300"/>
</div>

# 📡 NetBS

A pair of Python tools to monitor and visualize real-time network telemetry data such as bandwidth, latency, packet loss, and process usage.

* **NetBench**: Full-featured benchmark with 4K stress test.
* **NetScope**: Lightweight monitor for passive, long-term use.

---

## ✨ Features

### 📈 Common Features (Both Tools)

* Realtime download/upload bandwidth monitoring
* One-time upload test via `httpbin.org`
* Public IP & geolocation (city/country)
* Latency, jitter, packet loss via ping
* System resource usage: CPU & RAM
* Interface health (errors, drops)
* Network info: SSID, IP, gateway, DNS (IPv4 & IPv6)
* Per-process bandwidth tracking (top 5)
* Live terminal UI (powered by `rich`)
* Logging to `.csv`, `.json`, and `.png`
* CLI support for thresholds, intervals, history limit

### 💪 NetBench Exclusive

* Simulated 4K video streaming as **download stress test**

### 📊 NetScope Exclusive

* Passive-only monitor (no stress test)
* Periodic Speedtest.net integration (every 10 minutes)
* TCP/UDP connection count
* ASCII-based sparkline charts (minimal mode)
* Headless & power-efficient optimized

---

## ⬆️ Installation

```bash
git clone https://github.com/Sparkplugx1904/NetBench.git
cd NetBench
pip install -r requirements.txt
```

---

## ▶️ Usage

### 📡 Run NetBench

```bash
python NetBench.py [options]
```

### 📊 Run NetScope

```bash
python NetScope.py [options]
```

> Press `Ctrl+C` to stop monitoring. Output files saved in `/History/`.

### ⚙️ CLI Options

| Flag                    | Description                                 | Applies To    | Default    |
| ----------------------- | ------------------------------------------- | ------------- | ---------- |
| `-t`, `--threshold`     | Alert threshold in Mbps for download/upload | Both          | `1.0`      |
| `-s`, `--save-interval` | Telemetry write interval (in seconds)       | Both          | `300`      |
| `--history-limit`       | Number of points shown in sparkline         | Both          | `60`       |
| `--speedtest-mode`      | `periodic` or `once` (run Speedtest.net)    | NetScope only | `periodic` |

---

## 📁 Output Files

Saved in `/History/`:

* `SSID_timestamp.csv` – incremental telemetry log
* `SSID_timestamp.json` – full session history
* `SSID_timestamp.png` – dark-mode speed graph

Use manually:

```bash
python Graph.py History/SSID_timestamp.json
```

---

## ⚡ Requirements

* Python 3.9+
* `psutil`, `requests`, `ping3`, `speedtest-cli`, `matplotlib`, `rich`

See `requirements.txt` for full details.

---

## 📚 License

MIT License — see [LICENSE](LICENSE)

---

## 🌟 Contributing

Found a bug? Want to improve something?
Pull requests and issues are welcome!
