import os
import time
import threading
import psutil
import requests
import socket
import argparse
import json
from ping3 import ping
from datetime import datetime
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.console import Console
from rich.prompt import Prompt
from rich.traceback import install
from rich.text import Text  # Tambahkan ini
import matplotlib
matplotlib.use("Agg")  # Tambahkan ini sebelum import pyplot
import matplotlib.pyplot as plt
import speedtest
import subprocess
import sys  # Tambahkan ini

# Definisikan base_dir di awal file
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

install()
console = Console()

# === Global Telemetry ===
telemetry_data = {
    "ssid": "Unknown",
    "manufacturer": "Unknown",
    "ip": "0.0.0.0",
    "public_ip": "Unknown",
    "country": "Unknown",
    "city": "Unknown",
    "subnet": "Unknown",
    "gateway": "Unknown",
    "dns1": "Unknown",
    "dns2": "Unknown",
    "download": 0.0,
    "upload": 0.0,
    "top_download": 0.0,
    "top_upload": 0.0,
    "latency": 0.0,
    "jitter": 0.0,
    "packet_loss": 0.0,
    "sent": 0.0,
    "recv": 0.0,
    "cpu": 0.0,
    "memory": 0.0,
    "rssi": "Unknown",
    "channel": "Unknown",
    "frequency": "Unknown",
    "process_bandwidth": [],  # list of (pid, name, up_mbps, down_mbps)
    "active_tcp": 0,
    "active_udp": 0,
    "errors_in": 0,
    "errors_out": 0,
    "drop_in": 0,
    "drop_out": 0,
    "history": [],  # [(time, d_mbps, u_mbps)]
    "upload_test_speed": 0.0,  # bps
    "upload_test_running": False,
    "speedtest_download": 0.0,
    "speedtest_upload": 0.0,
}

start_time = time.time()
initial_sent = 0
initial_recv = 0
interface = None
alert_threshold = 1.0  # Mbps
save_interval = 300  # seconds
history_limit = 60  # number of points for sparkline

# === Utility functions ===
def format_speed(bps):
    if bps >= 1_000_000_000:
        return f"{bps / 1_000_000_000:.2f} Gbps"
    elif bps >= 1_000_000:
        return f"{bps / 1_000_000:.2f} Mbps"
    elif bps >= 1_000:
        return f"{bps / 1_000:.2f} Kbps"
    return f"{bps:.2f} bps"

# Tambahkan fungsi ascii_sparkline
def ascii_sparkline(data, width=30):
    if not data:
        return ""
    bars = "▁▂▃▄▅▆▇█"
    mn, mx = min(data), max(data)
    if mx == mn:
        return bars[0] * min(len(data), width)
    scaled = [
        bars[int((v - mn) / (mx - mn) * (len(bars) - 1))]
        for v in data[-width:]
    ]
    return "".join(scaled)

# Get public IP and geolocation every 10 minutes
def update_public_ip():
    while True:
        try:
            resp = requests.get("https://api.ipify.org?format=json", timeout=5)
            telemetry_data["public_ip"] = resp.json().get("ip", "Unknown")
            geo = requests.get(f"http://ip-api.com/json/{telemetry_data['public_ip']}", timeout=5).json()
            telemetry_data["country"] = geo.get("country", "Unknown")
            telemetry_data["city"] = geo.get("city", "Unknown")
        except:
            telemetry_data["public_ip"] = "Unknown"
            telemetry_data["country"] = "Unknown"
            telemetry_data["city"] = "Unknown"
        time.sleep(600)

# Calculate jitter and packet loss via repeated ping
def update_ping_stats():
    count = 10
    interval = 0.2
    while True:
        rtts = []
        lost = 0
        for _ in range(count):
            res = ping("8.8.8.8", unit='ms')
            if res is None:
                lost += 1
            else:
                rtts.append(res)
            time.sleep(interval)
        if rtts:
            telemetry_data["latency"] = sum(rtts) / len(rtts)
            telemetry_data["jitter"] = (max(rtts) - min(rtts))
        else:
            telemetry_data["latency"] = 0.0
            telemetry_data["jitter"] = 0.0
        telemetry_data["packet_loss"] = (lost / count) * 100
        time.sleep(2)

# Update upload/download speed and system resource usage
def update_speed():
    global initial_sent, initial_recv
    if interface:
        counters = psutil.net_io_counters(pernic=True).get(interface)
    else:
        counters = psutil.net_io_counters()
    initial_sent = counters.bytes_sent
    initial_recv = counters.bytes_recv
    old_sent = counters.bytes_sent
    old_recv = counters.bytes_recv
    while True:
        time.sleep(1)
        if interface:
            counters = psutil.net_io_counters(pernic=True).get(interface)
        else:
            counters = psutil.net_io_counters()
        new_sent = counters.bytes_sent
        new_recv = counters.bytes_recv
        upload_bps = (new_sent - old_sent) * 8
        download_bps = (new_recv - old_recv) * 8
        telemetry_data["upload"] = upload_bps
        telemetry_data["download"] = download_bps
        telemetry_data["top_upload"] = max(telemetry_data["top_upload"], upload_bps)
        telemetry_data["top_download"] = max(telemetry_data["top_download"], download_bps)
        telemetry_data["sent"] = (new_sent - initial_sent) / (1024 ** 2)
        telemetry_data["recv"] = (new_recv - initial_recv) / (1024 ** 2)
        t = time.time() - start_time
        telemetry_data["history"].append((t, download_bps / 1e6, upload_bps / 1e6))
        if len(telemetry_data["history"]) > 3600:
            telemetry_data["history"].pop(0)
        # Append to files
        append_telemetry_files(t, download_bps / 1e6, upload_bps / 1e6)
        old_sent, old_recv = new_sent, new_recv
        # update CPU and memory
        telemetry_data["cpu"] = psutil.cpu_percent(interval=None)
        telemetry_data["memory"] = psutil.virtual_memory().percent
        # update interface stats
        nic_stats = psutil.net_io_counters(pernic=True).get(interface) if interface else None
        if nic_stats:
            telemetry_data["errors_in"] = nic_stats.errin
            telemetry_data["errors_out"] = nic_stats.errout
            telemetry_data["drop_in"] = nic_stats.dropin
            telemetry_data["drop_out"] = nic_stats.dropout
        # update connection counts
        telemetry_data["active_tcp"] = len(psutil.net_connections(kind="tcp"))
        telemetry_data["active_udp"] = len(psutil.net_connections(kind="udp"))
        # per-process bandwidth
        pb = []
        for proc in psutil.process_iter(attrs=['pid','name']):
            try:
                io = proc.io_counters()
                # approximate by dividing total bytes by uptime
                uptime = time.time() - proc.create_time()
                up_mbps = (io.bytes_sent * 8 / uptime) / 1e6 if uptime>0 else 0
                down_mbps = (io.bytes_recv * 8 / uptime) / 1e6 if uptime > 0 else 0
                if up_mbps>0.1 or down_mbps>0.1:
                    pb.append((proc.pid, proc.info['name'], up_mbps, down_mbps))
            except:
                continue
        pb.sort(key=lambda x: (x[2]+x[3]), reverse=True)
        telemetry_data["process_bandwidth"] = pb[:5]

csv_file_path = None
json_file_path = None

def init_telemetry_files():
    global csv_file_path, json_file_path
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ssid = telemetry_data.get('ssid', 'Unknown').replace(" ", "_")
    folder = os.path.join(base_dir, "History")  # Ganti ke base_dir
    os.makedirs(folder, exist_ok=True)
    base_filename = f"{ssid}_{timestamp}"
    csv_file_path = os.path.join(folder, f"{base_filename}.csv")
    json_file_path = os.path.join(folder, f"{base_filename}.json")
    # Create and write CSV header
    with open(csv_file_path, "w") as f:
        f.write("Time (s),Download (Mbps),Upload (Mbps)\n")
    # Create initial JSON
    with open(json_file_path, "w") as f:
        json.dump({"history": []}, f, indent=2)

def append_telemetry_files(t, d, u):
    # Append to CSV
    if csv_file_path:
        try:
            with open(csv_file_path, "a") as f:
                f.write(f"{t:.2f},{d:.3f},{u:.3f}\n")
        except Exception as e:
            console.log(f"[red]Failed to append CSV:[/red] {e}")
    # Update JSON (overwrite with full history)
    if json_file_path:
        try:
            # Read existing JSON
            with open(json_file_path, "r") as f:
                data = json.load(f)
            if "history" not in data:
                data["history"] = []
            data["history"].append([t, d, u])
            with open(json_file_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            console.log(f"[red]Failed to update JSON:[/red] {e}")

def save_telemetry_plot_from_json():
    if not json_file_path:
        return
    try:
        with open(json_file_path, "r") as f:
            data = json.load(f)
        hist = data.get("history", [])
        if not hist:
            return
        times = [t for t, _, _ in hist]
        downloads = [d for _, d, _ in hist]
        uploads = [u for _, _, u in hist]
        ssid = telemetry_data.get('ssid', 'Unknown').replace(" ", "_")
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        folder = os.path.join(base_dir, "History")  # Ganti ke base_dir
        os.makedirs(folder, exist_ok=True)
        base_filename = f"{ssid}_{timestamp}_plot"
        png_path = os.path.join(folder, f"{base_filename}.png")
        plt.figure(figsize=(10, 5))
        ax = plt.gca()
        ax.set_facecolor("#23272e")  # dark gray background
        plt.gcf().patch.set_facecolor("#23272e")
        # Garis download magenta, upload hijau
        plt.plot(times, downloads, label="Download (Mbps)", color="magenta")
        plt.plot(times, uploads, label="Upload (Mbps)", color="lime")
        # Grid dan teks putih
        plt.xlabel("Time (s)", color="white")
        plt.ylabel("Speed (Mbps)", color="white")
        plt.title(f"Network Speed Telemetry - {ssid}", color="white")
        plt.legend(facecolor="#23272e", edgecolor="white", labelcolor="white")
        plt.grid(True, color="white", alpha=0.2)
        # Set semua axis label dan tick ke putih
        ax.tick_params(axis='x', colors='white')
        ax.tick_params(axis='y', colors='white')
        ax.spines['bottom'].set_color('white')
        ax.spines['top'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['right'].set_color('white')
        plt.tight_layout()
        plt.savefig(png_path, facecolor=plt.gcf().get_facecolor())
        plt.close()
        console.print(f"[bold green]Saved plot to {png_path}[/bold green]")
    except Exception as e:
        console.log(f"[red]Failed to save plot:[/red] {e}")

# Periodic save to CSV and JSON
def save_periodic():
    while True:
        time.sleep(save_interval)
        save_telemetry_history()

# One-time upload test
def run_one_time_upload_test(duration=10):
    telemetry_data["upload_test_running"] = True
    url = "https://httpbin.org/post"
    dummy_data = b"x" * (1024 * 512)
    end_time = time.time() + duration
    session = requests.Session()
    bytes_sent_total = 0
    bytes_sent_since_last = 0
    last_update = time.time()
    while time.time() < end_time:
        try:
            session.post(url, data=dummy_data, timeout=10)
            bytes_sent_total += len(dummy_data)
            bytes_sent_since_last += len(dummy_data)
        except:
            time.sleep(1)
        now = time.time()
        if now - last_update >= 1.0:
            telemetry_data["upload_test_speed"] = bytes_sent_since_last * 8
            bytes_sent_since_last = 0
            last_update = now
    telemetry_data["upload_test_speed"] = (bytes_sent_total * 8) / duration
    telemetry_data["upload_test_running"] = False

# Speedtest integration every 10 minutes
def run_speedtest_periodic():
    while True:
        try:
            st = speedtest.Speedtest()
            st.get_best_server()
            dl = st.download()
            up = st.upload()
            telemetry_data["speedtest_download"] = dl
            telemetry_data["speedtest_upload"] = up
        except:
            telemetry_data["speedtest_download"] = 0
            telemetry_data["speedtest_upload"] = 0
        time.sleep(600)  # 10 menit

def run_speedtest_once():
    try:
        st = speedtest.Speedtest()
        st.get_best_server()
        dl = st.download()
        up = st.upload()
        telemetry_data["speedtest_download"] = dl
        telemetry_data["speedtest_upload"] = up
    except:
        telemetry_data["speedtest_download"] = 0
        telemetry_data["speedtest_upload"] = 0

# Get WiFi info (RSSI, channel, freq)
def update_wifi_info():
    while True:
        ssid = "Unknown"
        manufacturer = "Unknown"
        rssi = "Unknown"
        channel = "Unknown"
        frequency = "Unknown"
        try:
            if os.name == "nt":
                out = subprocess.check_output("netsh wlan show interfaces", shell=True).decode(errors="ignore")
                for line in out.splitlines():
                    if "SSID" in line and "BSSID" not in line:
                        ssid = line.split(":",1)[-1].strip()
                    if "Signal" in line:
                        rssi = line.split(":",1)[-1].strip()
                    if "Radio type" in line:
                        manufacturer = line.split(":",1)[-1].strip()
            else:
                try:
                    out = subprocess.check_output("iwgetid -r", shell=True).decode().strip()
                    if out:
                        ssid = out
                except:
                    pass
                try:
                    out = subprocess.check_output("iwconfig 2>/dev/null", shell=True).decode()
                    for line in out.splitlines():
                        if "Channel" in line:
                            parts = line.split()
                            for p in parts:
                                if p.startswith("Channel"):
                                    channel = p.split(":")[-1]
                                if "Frequency" in p:
                                    frequency = p.split(":")[-1]
                        if "Signal level" in line:
                            rssi = line.split("Signal level=")[-1].split()[0]
                except:
                    pass
        except:
            pass
        telemetry_data["ssid"] = ssid
        telemetry_data["manufacturer"] = manufacturer
        telemetry_data["rssi"] = rssi
        telemetry_data["channel"] = channel
        telemetry_data["frequency"] = frequency
        time.sleep(5)

def update_wifi_info_once():
    ssid = "Unknown"
    manufacturer = "Unknown"
    rssi = "Unknown"
    channel = "Unknown"
    frequency = "Unknown"
    try:
        if os.name == "nt":
            out = subprocess.check_output("netsh wlan show interfaces", shell=True).decode(errors="ignore")
            for line in out.splitlines():
                if "SSID" in line and "BSSID" not in line:
                    ssid = line.split(":",1)[-1].strip()
                if "Signal" in line:
                    rssi = line.split(":",1)[-1].strip()
                if "Radio type" in line:
                    manufacturer = line.split(":",1)[-1].strip()
        else:
            try:
                out = subprocess.check_output("iwgetid -r", shell=True).decode().strip()
                if out:
                    ssid = out
            except:
                pass
            try:
                out = subprocess.check_output("iwconfig 2>/dev/null", shell=True).decode()
                for line in out.splitlines():
                    if "Channel" in line:
                        parts = line.split()
                        for p in parts:
                            if p.startswith("Channel"):
                                channel = p.split(":")[-1]
                            if "Frequency" in p:
                                frequency = p.split(":")[-1]
                    if "Signal level" in line:
                        rssi = line.split("Signal level=")[-1].split()[0]
            except:
                pass
    except:
        pass
    telemetry_data["ssid"] = ssid
    telemetry_data["manufacturer"] = manufacturer
    telemetry_data["rssi"] = rssi
    telemetry_data["channel"] = channel
    telemetry_data["frequency"] = frequency

# Get network interface info (ip, subnet, gateway, dns)
def get_network_info():
    global interface
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    choices = [name for name, stat in stats.items() if stat.isup and name != "lo"]
    if not choices:
        choices = list(addrs.keys())
    console.print("Available interfaces:")
    for i, name in enumerate(choices, 1):
        console.print(f"  [green]{i}[/green]. {name}")
    choice = Prompt.ask("Select interface number to monitor", choices=[str(i) for i in range(1, len(choices)+1)], default="1")
    interface = choices[int(choice)-1]
    for snic in addrs.get(interface, []):
        if snic.family == socket.AF_INET:
            telemetry_data["ip"] = snic.address
            telemetry_data["subnet"] = snic.netmask
            break
    try:
        if os.name == "nt":
            out = subprocess.check_output("route print 0.0.0.0", shell=True).decode(errors="ignore")
            gw = "Unknown"
            for line in out.splitlines():
                if line.strip().startswith("0.0.0.0"):
                    parts = line.split()
                    if len(parts) >= 3:
                        gw = parts[2]
                        break
            telemetry_data["gateway"] = gw
        else:
            out = subprocess.check_output("ip route", shell=True).decode(errors="ignore")
            gw = "Unknown"
            for line in out.splitlines():
                if line.startswith("default via"):
                    gw = line.split()[2]
                    break
            telemetry_data["gateway"] = gw
    except:
        telemetry_data["gateway"] = "Unknown"
    try:
        dns1 = dns2 = "Unknown"
        dns_ipv4 = []
        dns_ipv6 = []
        if os.name == "nt":
            out = subprocess.check_output("ipconfig /all", shell=True).decode(errors="ignore")
            capture = False
            for line in out.splitlines():
                if "DNS Servers" in line:
                    capture = True
                    parts = line.split(":",1)
                    if len(parts)>1 and parts[1].strip():
                        ip = parts[1].strip()
                        if ip.count(".")==3:
                            dns_ipv4.append(ip)
                        elif ":" in ip:
                            dns_ipv6.append(ip)
                    continue
                if capture:
                    if line.strip()=="" or (line and not line.startswith(" ")):
                        break
                    ip = line.strip()
                    if ip:
                        if ip.count(".")==3:
                            dns_ipv4.append(ip)
                        elif ":" in ip:
                            dns_ipv6.append(ip)
            if dns_ipv4:
                dns1 = dns_ipv4[0]
                if len(dns_ipv4)>1:
                    dns2 = dns_ipv4[1]
            elif dns_ipv6:
                dns1 = dns_ipv6[0]
                if len(dns_ipv6)>1:
                    dns2 = dns_ipv6[1]
        else:
            with open("/etc/resolv.conf") as f:
                for line in f:
                    if line.startswith("nameserver"):
                        ip = line.split()[1]
                        if ip.count(".")==3:
                            dns_ipv4.append(ip)
                        elif ":" in ip:
                            dns_ipv6.append(ip)
            if dns_ipv4:
                dns1 = dns_ipv4[0]
                if len(dns_ipv4)>1:
                    dns2 = dns_ipv4[1]
            elif dns_ipv6:
                dns1 = dns_ipv6[0]
                if len(dns_ipv6)>1:
                    dns2 = dns_ipv6[1]
        telemetry_data["dns1"] = dns1
        telemetry_data["dns2"] = dns2
    except:
        telemetry_data["dns1"] = "Unknown"
        telemetry_data["dns2"] = "Unknown"

# Save telemetry history to CSV and JSON, and plot
def save_telemetry_history():
    runtime = int(time.time() - start_time)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ssid = telemetry_data.get('ssid', 'Unknown').replace(" ", "_")
    folder = os.path.join(base_dir, "History")  # Ganti ke base_dir
    os.makedirs(folder, exist_ok=True)

    base_filename = f"{ssid}_{timestamp}_{runtime}s"
    csv_path = os.path.join(folder, f"{base_filename}.csv")
    json_path = os.path.join(folder, f"{base_filename}.json")
    png_path = os.path.join(folder, f"{base_filename}.png")

    # Save CSV
    try:
        with open(csv_path, "w") as f:
            f.write("Time (s),Download (Mbps),Upload (Mbps)\n")
            for t, d, u in telemetry_data["history"]:
                f.write(f"{t:.2f},{d:.3f},{u:.3f}\n")
    except Exception as e:
        console.log(f"[red]Failed to save CSV:[/red] {e}")

    # Save JSON
    try:
        with open(json_path, "w") as f:
            json.dump(telemetry_data, f, indent=2)
    except Exception as e:
        console.log(f"[red]Failed to save JSON:[/red] {e}")

    # Save plot
    try:
        times = [t for t, _, _ in telemetry_data["history"]]
        downloads = [d for _, d, _ in telemetry_data["history"]]
        uploads = [u for _, _, u in telemetry_data["history"]]
        plt.figure(figsize=(10, 5))
        plt.plot(times, downloads, label="Download (Mbps)", color="blue")
        plt.plot(times, uploads, label="Upload (Mbps)", color="green")
        plt.xlabel("Time (s)")
        plt.ylabel("Speed (Mbps)")
        plt.title(f"Network Speed Telemetry - {ssid}")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(png_path)
        plt.close()
    except Exception as e:
        console.log(f"[red]Failed to save plot:[/red] {e}")


# Display UI with Rich
def telemetry_ui():
    with Live(refresh_per_second=1) as live:
        while True:
            tbl = Table(title="📶 Net Benchmark Monitor", expand=True, box=box.SIMPLE_HEAVY)
            tbl.add_column("Metric", style="bold cyan")
            tbl.add_column("Value", style="bold magenta")
            # Basic Info
            tbl.add_row("SSID", telemetry_data['ssid'])
            tbl.add_row("Manufacturer", telemetry_data['manufacturer'])
            tbl.add_row("Local IP", telemetry_data['ip'])
            tbl.add_row("Public IP", telemetry_data['public_ip'])
            tbl.add_row("Location", f"{telemetry_data['city']}, {telemetry_data['country']}")
            tbl.add_row("Subnet Mask", telemetry_data['subnet'])
            tbl.add_row("Default Gateway", telemetry_data['gateway'])
            tbl.add_row("DNS1", telemetry_data['dns1'])
            tbl.add_row("DNS2", telemetry_data['dns2'])
            # WiFi Info
            tbl.add_row("Signal (RSSI)", telemetry_data['rssi'])
            tbl.add_row("Channel", telemetry_data['channel'])
            tbl.add_row("Frequency", telemetry_data['frequency'])
            # Speed Info
            dl_mbps = telemetry_data['download']/1e6
            ul_mbps = telemetry_data['upload']/1e6
            dl_style = ""
            ul_style = ""
            if dl_mbps < alert_threshold:
                dl_style = "bold red"
            elif dl_mbps < alert_threshold*10:
                dl_style = "yellow"
            else:
                dl_style = "green"
            if ul_mbps < alert_threshold:
                ul_style = "bold red"
            elif ul_mbps < alert_threshold*10:
                ul_style = "yellow"
            else:
                ul_style = "green"
            download_str = Text(f"{format_speed(telemetry_data['download'])} / {format_speed(telemetry_data['top_download'])}", style=dl_style)
            if telemetry_data["upload_test_running"]:
                upload_str = Text(f"Testing... {format_speed(telemetry_data['upload_test_speed'])}", style=ul_style)
            else:
                upload_str = Text(f"{format_speed(telemetry_data['upload'])} / {format_speed(telemetry_data['top_upload'])}", style=ul_style)
            tbl.add_row("Download Speed", download_str)
            tbl.add_row("Upload Speed", upload_str)
            tbl.add_row("Speedtest DL", format_speed(telemetry_data['speedtest_download']))
            tbl.add_row("Speedtest UL", format_speed(telemetry_data['speedtest_upload']))
            # Latency Stats
            tbl.add_row("Latency", f"{telemetry_data['latency']:.2f} ms")
            tbl.add_row("Jitter", f"{telemetry_data['jitter']:.2f} ms")
            tbl.add_row("Packet Loss", f"{telemetry_data['packet_loss']:.2f} %")
            # Resource Usage
            tbl.add_row("CPU Usage", f"{telemetry_data['cpu']:.1f} %")
            tbl.add_row("Memory Usage", f"{telemetry_data['memory']:.1f} %")
            # Data Usage
            tbl.add_row("Data Sent", f"{telemetry_data['sent']:.2f} MB")
            tbl.add_row("Data Received", f"{telemetry_data['recv']:.2f} MB")
            # Connection Stats
            tbl.add_row("Active TCP Conns", str(telemetry_data['active_tcp']))
            tbl.add_row("Active UDP Conns", str(telemetry_data['active_udp']))
            tbl.add_row("Errors In/Out", f"{telemetry_data['errors_in']}/{telemetry_data['errors_out']}")
            tbl.add_row("Dropped In/Out", f"{telemetry_data['drop_in']}/{telemetry_data['drop_out']}")
            # Per-process bandwidth
            pb_lines = []
            for pid, name, up_m, down_m in telemetry_data['process_bandwidth']:
                pb_lines.append(f"{pid}:{name} ↑{up_m:.2f}Mbps ↓{down_m:.2f}Mbps")
            tbl.add_row("Top Processes", "\n".join(pb_lines) if pb_lines else "N/A")
            # ASCII Sparklines for last history_limit points
            hist = telemetry_data['history'][-history_limit:]
            dl_vals = [d for _, d, _ in hist]
            ul_vals = [u for _, _, u in hist]
            if dl_vals:
                # dl_spark = Sparkline(dl_vals, max_width=history_limit)  # DIHAPUS
                dl_spark = ascii_sparkline(dl_vals, width=history_limit)
                tbl.add_row("DL Sparkline", dl_spark)
            else:
                tbl.add_row("DL Sparkline", "N/A")
            if ul_vals:
                # ul_spark = Sparkline(ul_vals, max_width=history_limit)  # DIHAPUS
                ul_spark = ascii_sparkline(ul_vals, width=history_limit)
                tbl.add_row("UL Sparkline", ul_spark)
            else:
                tbl.add_row("UL Sparkline", "N/A")
            live.update(Panel(tbl))
            time.sleep(1)

# CLI and Main
def main():
    parser = argparse.ArgumentParser(description="Net Benchmark Extended Monitor")
    parser.add_argument("-t", "--threshold", type=float, default=1.0, help="Alert threshold Mbps")
    parser.add_argument("-s", "--save-interval", type=int, default=300, help="Periodic save interval seconds")
    parser.add_argument("--history-limit", type=int, default=60, help="Number of points for sparkline")
    parser.add_argument("--speedtest-mode", choices=["periodic", "once"], default="periodic",
                        help="Speedtest mode: periodic (default) or once at startup")
    args = parser.parse_args()
    global alert_threshold, save_interval, history_limit
    alert_threshold = args.threshold
    save_interval = args.save_interval
    history_limit = args.history_limit
    get_network_info()
    update_wifi_info_once()  # Pastikan SSID sudah terisi sebelum init file
    init_telemetry_files()
    # Threads
    threading.Thread(target=update_public_ip, daemon=True).start()
    threading.Thread(target=update_ping_stats, daemon=True).start()
    threading.Thread(target=update_speed, daemon=True).start()
    threading.Thread(target=run_one_time_upload_test, args=(10,), daemon=True).start()
    if args.speedtest_mode == "periodic":
        threading.Thread(target=run_speedtest_periodic, daemon=True).start()
    else:
        run_speedtest_once()
    threading.Thread(target=update_wifi_info, daemon=True).start()
    # Remove save_periodic thread, handled by append_telemetry_files
    try:
        telemetry_ui()
    except KeyboardInterrupt:
        save_telemetry_plot_from_json()
        console.print("\n[bold green]Telemetry plot saved. Exiting.[/bold green]")

if __name__ == "__main__":
    main()



# Tambahkan argumen CLI baru --speedtest-mode dengan pilihan periodic (default) atau once.
# Ubah fungsi main() agar hanya menjalankan thread speedtest periodik jika mode periodic, dan jika once hanya jalankan speedtest sekali di awal.
# Ubah interval sleep di run_speedtest_periodic ke 600 detik (10 menit) agar sesuai deskripsi.