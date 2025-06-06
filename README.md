# 📶 NetBench & NetScope

A pair of Python tools to monitor and visualize real-time network telemetry data such as bandwidth, latency, packet loss, and process usage. NetBench includes a built-in stress test, while NetScope offers a lightweight alternative for long-term monitoring.

## Features

### NetBench

* Real-time monitoring of download/upload speeds
* One-time upload test via `httpbin.org`
* Background streaming download simulation (4K video)
* Public IP detection and geolocation (city & country)
* Detailed network info: SSID, IP, gateway, DNS (IPv4 & IPv6)
* Latency, jitter, and packet loss statistics via ping
* CPU and memory usage tracking
* Interface error/drop stats
* Data logging to CSV, JSON, and PNG chart
* Live terminal UI (via `rich`)
* CLI arguments for thresholds, intervals, history

### NetScope

* All NetBench features **except** traffic simulation
* Periodic Speedtest.net measurement every 10 mins
* Per-process bandwidth tracking (top 5 processes)
* TCP/UDP connection statistics
* Terminal-friendly ASCII sparklines
* Optimized for headless or background usage

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/network-monitor-suite.git
   cd network-monitor-suite
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Run NetBench

```bash
python NetBench.py -t 1.0 -s 300 --history-limit 60
```

### Run NetScope

```bash
python NetScope.py -t 1.0 -s 300 --history-limit 60
```

> Press `Ctrl+C` to stop monitoring and save data to `/History/`

## Requirements

* Python 3.9 or newer
* Dependencies:

  * psutil
  * requests
  * ping3
  * speedtest-cli
  * matplotlib
  * rich

See `requirements.txt` for full list.

## Output Files

Saved in the `/History/` folder:

* `SSID_timestamp.csv` – raw telemetry log
* `SSID_timestamp.json` – full session snapshot
* `SSID_timestamp.png` – bandwidth history chart

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Feel free to open issues or submit pull requests to improve or extend this project.

---

## Contact

Created with ❤️ by **Sparkplugx1904**
