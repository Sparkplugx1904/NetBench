# 📶 Internet Benchmark

A Python tool to monitor and visualize real-time WiFi benchmark telemetry data such as download/upload speeds, latency, IP, and data usage, with a built-in one-time upload test and continuous traffic generation.

## Features

- Real-time monitoring of download/upload speeds and latency
- One-time upload speed test on startup
- Background streaming download traffic simulation
- Live terminal UI with detailed network info
- Data logging and speed history visualization as CSV and PNG charts
- Supports Windows/Linux (requires Python 3.7+)

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/wifi-telemetry-monitor.git
   cd wifi-telemetry-monitor
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the main script:

```bash
python telemetry_monitor.py
```

Press `Ctrl+C` to exit and save telemetry history.

## Requirements

- Python 3.7 or newer
- `psutil`
- `requests`
- `ping3`
- `rich`
- `matplotlib`

See `requirements.txt` for full list.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Feel free to open issues or submit pull requests!

---

## Contact

Created with love by Sparkplugx1904❤️.

