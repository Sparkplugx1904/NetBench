import os
import sys
import json
from datetime import datetime
import matplotlib.pyplot as plt

def load_telemetry_data(json_path):
    with open(json_path, "r") as f:
        data = json.load(f)
    return data.get("history", []), data.get("ssid", "Unknown")

def create_and_save_plot(json_path, history, ssid):
    if not history:
        print("[!] No history data found.")
        return

    times = [t for t, _, _ in history]
    downloads = [d for _, d, _ in history]
    uploads = [u for _, _, u in history]

    # Output path setup
    output_folder = os.path.dirname(os.path.abspath(json_path))
    ssid_clean = ssid.replace(" ", "_")
    base_filename = os.path.splitext(os.path.basename(json_path))[0]
    png_path = os.path.join(output_folder, f"{base_filename}.png")

    # Plotting with dark mode theme
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#222326")
    ax.set_facecolor("#222326")

    ax.plot(times, downloads, label="Download (Mbps)", color="magenta", linewidth=2)
    ax.plot(times, uploads, label="Upload (Mbps)", color="lime", linewidth=2)

    ax.set_xlabel("Time (s)", color="white")
    ax.set_ylabel("Speed (Mbps)", color="white")
    ax.set_title(f"Network Speed Telemetry - {ssid}", color="white")

    ax.legend(facecolor="#222326", edgecolor="white", labelcolor="white")
    ax.grid(True, color="white", alpha=0.2)
    ax.tick_params(axis='x', colors='white')
    ax.tick_params(axis='y', colors='white')

    for spine in ax.spines.values():
        spine.set_color("white")

    plt.tight_layout()
    plt.savefig(png_path)
    plt.close()

    print(f"[✓] Plot saved to: {png_path}")

def main():
    if len(sys.argv) != 2 or not sys.argv[1].endswith(".json"):
        print("Usage: python graph.py <namefile>.json")
        return

    json_path = sys.argv[1]
    if not os.path.exists(json_path):
        print(f"[!] File not found: {json_path}")
        return

    try:
        history, ssid = load_telemetry_data(json_path)
        create_and_save_plot(json_path, history, ssid)
    except Exception as e:
        print(f"[!] Error: {e}")

if __name__ == "__main__":
    main()
