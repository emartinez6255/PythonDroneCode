import csv
import os
import time
import statistics
import matplotlib.pyplot as plt


# =========================
# CONFIG
# =========================
RUNS = 5  # number of repetitions per test
RESULTS_DIR = "results"

os.makedirs(RESULTS_DIR, exist_ok=True)


# =========================
# HELPERS
# =========================
def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


# =========================
# SIMULATED PLACEHOLDERS
# (replace with your real functions)
# =========================

def run_tcp_chat_test(test_type):
    # replace with actual socket timing logic
    time.sleep(0.05)
    return 10 + (hash(test_type) % 5)


def run_udp_chat_test(test_type):
    time.sleep(0.03)
    return 8 + (hash(test_type) % 5)


def run_tcp_file_test(size):
    time.sleep(0.1)
    return 100 + (size % 50)


def run_udp_file_test(size):
    time.sleep(0.08)
    return 120 + (size % 50)


# =========================
# CHAT EXPERIMENT
# =========================
def run_chat_experiment():
    test_types = ["burst", "32", "256", "1024"]

    tcp_rows = []
    udp_rows = []

    for test in test_types:
        tcp_results = []
        udp_results = []

        for _ in range(RUNS):
            tcp_results.append(run_tcp_chat_test(test))
            udp_results.append(run_udp_chat_test(test))

        tcp_avg = statistics.mean(tcp_results)
        udp_avg = statistics.mean(udp_results)

        tcp_rows.append([test, tcp_avg])
        udp_rows.append([test, udp_avg])

    write_csv(f"{RESULTS_DIR}/tcp_chat.csv", ["test", "latency"], tcp_rows)
    write_csv(f"{RESULTS_DIR}/udp_chat.csv", ["test", "latency"], udp_rows)


# =========================
# FILE EXPERIMENT
# =========================
def run_file_experiment():
    sizes = [102400, 1048576, 5242880]

    tcp_rows = []
    udp_rows = []

    for size in sizes:
        tcp_results = []
        udp_results = []

        for _ in range(RUNS):
            tcp_results.append(run_tcp_file_test(size))
            udp_results.append(run_udp_file_test(size))

        tcp_avg = statistics.mean(tcp_results)
        udp_avg = statistics.mean(udp_results)

        tcp_rows.append([size, tcp_avg])
        udp_rows.append([size, udp_avg])

    write_csv(f"{RESULTS_DIR}/tcp_file.csv", ["size", "throughput"], tcp_rows)
    write_csv(f"{RESULTS_DIR}/udp_file.csv", ["size", "throughput"], udp_rows)


# =========================
# GRAPHING (WITH ERROR BARS)
# =========================
def plot_results():
    import numpy as np

    # ---- CHAT ----
    def load(file):
        x, y = [], []
        with open(file) as f:
            r = csv.reader(f)
            next(r)
            for row in r:
                x.append(row[0])
                y.append(float(row[1]))
        return x, y

    tcp_x, tcp_y = load(f"{RESULTS_DIR}/tcp_chat.csv")
    udp_x, udp_y = load(f"{RESULTS_DIR}/udp_chat.csv")

    plt.figure()
    plt.plot(tcp_x, tcp_y, marker="o", label="TCP")
    plt.plot(udp_x, udp_y, marker="o", label="UDP")
    plt.title("Chat Latency (Averaged Runs)")
    plt.xlabel("Test Type")
    plt.ylabel("Latency")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{RESULTS_DIR}/chat_comparison.png")


    # ---- FILE ----
    tcp_x, tcp_y = load(f"{RESULTS_DIR}/tcp_file.csv")
    udp_x, udp_y = load(f"{RESULTS_DIR}/udp_file.csv")

    plt.figure()
    plt.plot(tcp_x, tcp_y, marker="o", label="TCP")
    plt.plot(udp_x, udp_y, marker="o", label="UDP")
    plt.title("File Throughput (Averaged Runs)")
    plt.xlabel("File Size")
    plt.ylabel("Throughput")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{RESULTS_DIR}/file_comparison.png")


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    print("🚀 Running experiments...")

    run_chat_experiment()
    run_file_experiment()

    plot_results()

    print("✅ Done. Results saved in /results")