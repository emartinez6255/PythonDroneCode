import csv
import matplotlib.pyplot as plt
import re


# -----------------------------
# CHAT LOADER (UNCHANGED)
# -----------------------------
def load_chat(file):
    data = {}

    with open(file, "r") as f:
        reader = csv.reader(f)

        for row in reader:
            if len(row) < 3:
                continue

            test_type = row[1]
            value = float(row[2])

            if test_type not in data:
                data[test_type] = []

            data[test_type].append(value)

    return data


# -----------------------------
# SAFE FILE SIZE PARSER
# -----------------------------
def extract_size(value):
    """
    Handles:
    - 102400
    - test_100kb.dat
    """

    # Case 1: already numeric
    try:
        return int(value)
    except:
        pass

    # Case 2: filename like test_100kb.dat
    match = re.search(r'(\d+)', value)
    if match:
        num = int(match.group(1))

        # convert KB/MB style filenames
        if "kb" in value.lower():
            return num * 1024
        if "mb" in value.lower():
            return num * 1024 * 1024

        return num

    return 0


# -----------------------------
# FILE LOADER (FIXED)
# -----------------------------
def load_file(file):
    data = {}

    with open(file, "r") as f:
        reader = csv.reader(f)

        for row in reader:
            if len(row) < 4:
                continue

            size_raw = row[1]
            throughput = float(row[3])

            size = extract_size(size_raw)

            if size > 0:
                data[size] = throughput

    return data


# -----------------------------
# CHAT PLOT
# -----------------------------
tcp_chat = load_chat("results/tcp_chat.csv")
udp_chat = load_chat("results/udp_chat.csv")

chat_keys = sorted(set(tcp_chat.keys()) | set(udp_chat.keys()))

tcp_chat_vals = [
    sum(tcp_chat.get(k, [0])) / max(len(tcp_chat.get(k, [1])), 1)
    for k in chat_keys
]

udp_chat_vals = [
    sum(udp_chat.get(k, [0])) / max(len(udp_chat.get(k, [1])), 1)
    for k in chat_keys
]

plt.figure()
plt.plot(chat_keys, tcp_chat_vals, marker="o", label="TCP")
plt.plot(chat_keys, udp_chat_vals, marker="o", label="UDP")
plt.title("Chat Latency Comparison (TCP vs UDP)")
plt.xlabel("Test Type")
plt.ylabel("Latency (ms)")
plt.legend()
plt.tight_layout()
plt.savefig("results/chat_comparison.png")


# -----------------------------
# FILE PLOT (FIXED ROBUST)
# -----------------------------
tcp_file = load_file("results/tcp_file.csv")
udp_file = load_file("results/udp_file.csv")

file_sizes = sorted(set(tcp_file.keys()) | set(udp_file.keys()))

tcp_vals = [tcp_file.get(s, 0) for s in file_sizes]
udp_vals = [udp_file.get(s, 0) for s in file_sizes]

plt.figure()
plt.plot(file_sizes, tcp_vals, marker="o", label="TCP")
plt.plot(file_sizes, udp_vals, marker="o", label="UDP")
plt.title("File Throughput Comparison (TCP vs UDP)")
plt.xlabel("File Size (bytes)")
plt.ylabel("Throughput (KB/s)")
plt.legend()
plt.tight_layout()
plt.savefig("results/file_comparison.png")

print("✅ Chat + File comparison graphs generated successfully")