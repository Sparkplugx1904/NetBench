import os
import time
import threading
import psutil
import requests
import socket
from ping3 import ping
from datetime import datetime
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
import matplotlib.pyplot as plt

# === Global Telemetry ===
telemetry_data = {
    "ssid": "Unknown",
    "manufacturer": "Unknown",
    "ip": "0.0.0.0",
    "subnet": "Unknown",
    "gateway": "Unknown",
    "dns1": "Unknown",
    "dns2": "Unknown",
    "download": 0.0,
    "upload": 0.0,
    "top_download": 0.0,
    "top_upload": 0.0,
    "latency": 0.0,
    "sent": 0.0,
    "recv": 0.0,
    "history": [],
    "upload_test_speed": 0.0,  # new: upload test speed from initial upload test (bps)
    "upload_test_running": False,  # flag to indicate if upload test is running
}

start_time = time.time()

# Tambahkan variabel global untuk baseline
initial_sent = 0
initial_recv = 0

# === Utility functions ===
def format_speed(bps):
    if bps >= 1_000_000_000:
        return f"{bps / 1_000_000_000:.2f} Gbps"
    elif bps >= 1_000_000:
        return f"{bps / 1_000_000:.2f} Mbps"
    elif bps >= 1_000:
        return f"{bps / 1_000:.2f} Kbps"
    return f"{bps:.2f} bps"

def update_ping_ip():
    while True:
        try:
            telemetry_data["latency"] = ping("8.8.8.8", unit='ms') or 0.0
            telemetry_data["ip"] = socket.gethostbyname(socket.gethostname())
        except:
            telemetry_data["latency"] = 0.0
            telemetry_data["ip"] = "Unknown"
        time.sleep(3)

def update_speed():
    global initial_sent, initial_recv
    # Ambil baseline hanya sekali di awal
    if initial_sent == 0 and initial_recv == 0:
        counters = psutil.net_io_counters()
        initial_sent = counters.bytes_sent
        initial_recv = counters.bytes_recv
    old_sent = psutil.net_io_counters().bytes_sent
    old_recv = psutil.net_io_counters().bytes_recv
    while True:
        time.sleep(1)
        new_sent = psutil.net_io_counters().bytes_sent
        new_recv = psutil.net_io_counters().bytes_recv
        upload_bps = (new_sent - old_sent) * 8
        download_bps = (new_recv - old_recv) * 8

        telemetry_data["upload"] = upload_bps
        telemetry_data["download"] = download_bps
        telemetry_data["top_upload"] = max(telemetry_data["top_upload"], upload_bps)
        telemetry_data["top_download"] = max(telemetry_data["top_download"], download_bps)
        # Ubah: hanya selisih sejak program mulai
        telemetry_data["sent"] = (new_sent - initial_sent) / (1024 ** 2)
        telemetry_data["recv"] = (new_recv - initial_recv) / (1024 ** 2)
        telemetry_data["history"].append((time.time() - start_time, download_bps / 1e6, upload_bps / 1e6))

        old_sent, old_recv = new_sent, new_recv

def generate_download_traffic(duration=3600):
    url = "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
    end_time = time.time() + duration
    while time.time() < end_time:
        try:
            with requests.get(url, stream=True, timeout=10) as r:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if time.time() > end_time:
                        break
        except Exception as e:
            print(f"[!] Download streaming error: {e}")
            time.sleep(5)

def run_one_time_upload_test(duration=10):
    """
    Run upload test for 'duration' seconds.
    Update telemetry_data['upload_test_speed'] every second with current average upload speed.
    """
    telemetry_data["upload_test_running"] = True
    url = "https://httpbin.org/post"
    dummy_data = b"x" * (1024 * 512)  # 512 KB dummy data
    end_time = time.time() + duration
    session = requests.Session()
    bytes_sent_total = 0
    bytes_sent_since_last = 0
    last_update = time.time()

    while time.time() < end_time:
        try:
            resp = session.post(url, data=dummy_data, timeout=10)
            bytes_sent_total += len(dummy_data)
            bytes_sent_since_last += len(dummy_data)
        except Exception as e:
            print(f"[!] Upload streaming error (during test): {e}")
            time.sleep(1)
        
        now = time.time()
        if now - last_update >= 1.0:
            # Update upload_test_speed: bits per second in last 1 sec
            telemetry_data["upload_test_speed"] = bytes_sent_since_last * 8
            bytes_sent_since_last = 0
            last_update = now

    # Final update after test ends (average over whole duration)
    telemetry_data["upload_test_speed"] = (bytes_sent_total * 8) / duration
    telemetry_data["upload_test_running"] = False

def get_network_info():
    # Ambil info interface aktif
    try:
        addrs = psutil.net_if_addrs()
        gws = psutil.net_if_stats()
        # Pilih interface yang aktif dan bukan loopback
        iface = None
        for name, stat in gws.items():
            if stat.isup and name != "lo":
                iface = name
                break
        if iface is None:
            iface = list(addrs.keys())[0]

        # IP Address
        ip = "Unknown"
        subnet = "Unknown"
        for snic in addrs[iface]:
            if snic.family == socket.AF_INET:
                ip = snic.address
                subnet = snic.netmask
                break
        telemetry_data["ip"] = ip
        telemetry_data["subnet"] = subnet

        # Gateway (dinamis tanpa netifaces/msvc)
        try:
            if os.name == "nt":
                import subprocess
                output = subprocess.check_output("route print 0.0.0.0", shell=True).decode(errors="ignore")
                gw = "Unknown"
                for line in output.splitlines():
                    if line.strip().startswith("0.0.0.0"):
                        parts = line.split()
                        if len(parts) >= 3:
                            gw = parts[2]
                            break
                telemetry_data["gateway"] = gw
            else:
                import subprocess
                output = subprocess.check_output("ip route", shell=True).decode(errors="ignore")
                gw = "Unknown"
                for line in output.splitlines():
                    if line.startswith("default via"):
                        gw = line.split()[2]
                        break
                telemetry_data["gateway"] = gw
        except Exception:
            telemetry_data["gateway"] = "Unknown"

        # DNS (dinamis tanpa netifaces/msvc)
        try:
            dns1 = dns2 = "Unknown"
            dns1_ipv4 = dns2_ipv4 = "Unknown"
            dns1_ipv6 = dns2_ipv6 = "Unknown"
            if os.name == "nt":
                import subprocess
                output = subprocess.check_output("ipconfig /all", shell=True).decode(errors="ignore")
                dns_ipv4 = []
                dns_ipv6 = []
                dns_servers = []
                capture = False
                for line in output.splitlines():
                    if "DNS Servers" in line:
                        capture = True
                        parts = line.split(":", 1)
                        if len(parts) > 1 and parts[1].strip():
                            ip = parts[1].strip()
                            # Simpan urutan kemunculan
                            if ip.count(".") == 3:
                                dns_ipv4.append(ip)
                            elif ":" in ip:
                                dns_ipv6.append(ip)
                        continue
                    if capture:
                        if line.strip() == "" or (line and not line.startswith(" ")):
                            break
                        ip = line.strip()
                        if ip:
                            if ip.count(".") == 3:
                                dns_ipv4.append(ip)
                            elif ":" in ip:
                                dns_ipv6.append(ip)
                # Preferred = urutan pertama, Alternate = urutan kedua
                if len(dns_ipv4) > 0:
                    dns1_ipv4 = dns_ipv4[0]
                if len(dns_ipv4) > 1:
                    dns2_ipv4 = dns_ipv4[1]
                if len(dns_ipv6) > 0:
                    dns1_ipv6 = dns_ipv6[0]
                if len(dns_ipv6) > 1:
                    dns2_ipv6 = dns_ipv6[1]
                # Untuk kompatibilitas lama
                if len(dns_ipv4) > 0:
                    dns1 = dns_ipv4[0]
                elif len(dns_ipv6) > 0:
                    dns1 = dns_ipv6[0]
                if len(dns_ipv4) > 1:
                    dns2 = dns_ipv4[1]
                elif len(dns_ipv6) > 1:
                    dns2 = dns_ipv6[1]
            else:
                dns_ipv4 = []
                dns_ipv6 = []
                with open("/etc/resolv.conf") as f:
                    for line in f:
                        if line.startswith("nameserver"):
                            ip = line.split()[1]
                            if ip.count(".") == 3:
                                dns_ipv4.append(ip)
                            elif ":" in ip:
                                dns_ipv6.append(ip)
                if len(dns_ipv4) > 0:
                    dns1_ipv4 = dns_ipv4[0]
                if len(dns_ipv4) > 1:
                    dns2_ipv4 = dns_ipv4[1]
                if len(dns_ipv6) > 0:
                    dns1_ipv6 = dns_ipv6[0]
                if len(dns_ipv6) > 1:
                    dns2_ipv6 = dns_ipv6[1]
                # Untuk kompatibilitas lama
                if len(dns_ipv4) > 0:
                    dns1 = dns_ipv4[0]
                elif len(dns_ipv6) > 0:
                    dns1 = dns_ipv6[0]
                if len(dns_ipv4) > 1:
                    dns2 = dns_ipv4[1]
                elif len(dns_ipv6) > 1:
                    dns2 = dns_ipv6[1]
            telemetry_data["dns1"] = dns1
            telemetry_data["dns2"] = dns2
            telemetry_data["dns1_ipv4"] = dns1_ipv4
            telemetry_data["dns2_ipv4"] = dns2_ipv4
            telemetry_data["dns1_ipv6"] = dns1_ipv6
            telemetry_data["dns2_ipv6"] = dns2_ipv6
        except Exception:
            telemetry_data["dns1"] = "Unknown"
            telemetry_data["dns2"] = "Unknown"
            telemetry_data["dns1_ipv4"] = "Unknown"
            telemetry_data["dns2_ipv4"] = "Unknown"
            telemetry_data["dns1_ipv6"] = "Unknown"
            telemetry_data["dns2_ipv6"] = "Unknown"

        # SSID & Manufacturer (khusus WiFi, platform dependent)
        ssid = "Unknown"
        manufacturer = "Unknown"
        try:
            if os.name == "nt":
                import subprocess
                output = subprocess.check_output("netsh wlan show interfaces", shell=True).decode(errors="ignore")
                for line in output.splitlines():
                    if "SSID" in line and "BSSID" not in line:
                        ssid = line.split(":", 1)[-1].strip()
                    if "Radio type" in line:
                        manufacturer = line.split(":", 1)[-1].strip()
            elif os.name == "posix":
                import subprocess
                try:
                    output = subprocess.check_output("iwgetid -r", shell=True).decode().strip()
                    if output:
                        ssid = output
                except Exception:
                    pass
                try:
                    output = subprocess.check_output("iwconfig 2>/dev/null", shell=True).decode()
                    for line in output.splitlines():
                        if "IEEE" in line:
                            manufacturer = line.split()[1]
                            break
                except Exception:
                    pass
        except Exception:
            pass
        telemetry_data["ssid"] = ssid
        telemetry_data["manufacturer"] = manufacturer

    except Exception:
        telemetry_data["ssid"] = "Unknown"
        telemetry_data["manufacturer"] = "Unknown"
        telemetry_data["ip"] = "Unknown"
        telemetry_data["subnet"] = "Unknown"
        telemetry_data["gateway"] = "Unknown"
        telemetry_data["dns1"] = "Unknown"
        telemetry_data["dns2"] = "Unknown"

def telemetry_ui():
    with Live(refresh_per_second=1) as live:
        while True:
            table = Table(title="📶 WiFi Telemetry Monitor", expand=True)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")

            table.add_row("SSID", telemetry_data['ssid'])
            table.add_row("Manufacturer", telemetry_data['manufacturer'])
            table.add_row("IP Address", telemetry_data['ip'])
            table.add_row("Subnet Mask", telemetry_data['subnet'])
            table.add_row("Default Gateway", telemetry_data['gateway'])
            # Hanya tampilkan DNS IPv4 & IPv6
            table.add_row("DNS 1 IPv4", telemetry_data.get('dns1_ipv4', 'Unknown'))
            table.add_row("DNS 2 IPv4", telemetry_data.get('dns2_ipv4', 'Unknown'))
            table.add_row("DNS 1 IPv6", telemetry_data.get('dns1_ipv6', 'Unknown'))
            table.add_row("DNS 2 IPv6", telemetry_data.get('dns2_ipv6', 'Unknown'))

            download_str = f"{format_speed(telemetry_data['download'])} / {format_speed(telemetry_data['top_download'])}"

            # Jika upload test sedang berjalan, tampilkan upload_test_speed realtime,
            # kalau tidak tampilkan kecepatan upload normal dari psutil
            if telemetry_data["upload_test_running"]:
                upload_str = f"Testing... {format_speed(telemetry_data['upload_test_speed'])}"
            else:
                upload_str = f"{format_speed(telemetry_data['upload'])} / {format_speed(telemetry_data['top_upload'])}"

            table.add_row("Download Speed", download_str)
            table.add_row("Upload Speed", upload_str)
            table.add_row("Latency", f"{telemetry_data['latency']:.2f} ms")
            table.add_row("Data Sent", f"{telemetry_data['sent']:.2f} MB")
            table.add_row("Data Received", f"{telemetry_data['recv']:.2f} MB")

            live.update(Panel(table))
            time.sleep(1)

def save_telemetry_history():
    runtime = int(time.time() - start_time)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{telemetry_data['ssid']}_{runtime}s_{timestamp}.csv"
    chartname = filename.replace(".csv", ".png")

    folder = os.path.join(os.path.dirname(__file__), "History")
    os.makedirs(folder, exist_ok=True)

    filepath = os.path.join(folder, filename)
    chartpath = os.path.join(folder, chartname)

    with open(filepath, "w") as f:
        f.write("Seconds,Download(Mbps),Upload(Mbps)\n")
        for t, d, u in telemetry_data["history"]:
            f.write(f"{t:.1f},{d:.2f},{u:.2f}\n")

    # Plot graph
    times = [t for t, _, _ in telemetry_data["history"]]
    downloads = [d for _, d, _ in telemetry_data["history"]]
    uploads = [u for _, _, u in telemetry_data["history"]]

    plt.style.use('dark_background')
    plt.figure(figsize=(10, 5))
    plt.plot(times, downloads, label='Download (Mbps)', color='cyan')
    plt.plot(times, uploads, label='Upload (Mbps)', color='magenta')
    plt.xlabel("Time (s)")
    plt.ylabel("Speed (Mbps)")
    plt.title("Network Speed Telemetry")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(chartpath)
    plt.close()

# === Main Execution ===
if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    get_network_info()

    # Start one-time upload test in background thread (non-blocking)
    threading.Thread(target=run_one_time_upload_test, args=(10,), daemon=True).start()

    # Start download traffic generator in background
    threading.Thread(target=generate_download_traffic, args=(3600,), daemon=True).start()

    # Start continuous update threads for ping and speed (psutil)
    threading.Thread(target=update_ping_ip, daemon=True).start()
    threading.Thread(target=update_speed, daemon=True).start()

    try:
        telemetry_ui()
    except KeyboardInterrupt:
        save_telemetry_history()
        print("\nTelemetry data saved. Exiting.")
