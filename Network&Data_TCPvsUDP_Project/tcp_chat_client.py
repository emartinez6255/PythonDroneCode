import socket
import threading
import time
import csv
import os

HOST = '127.0.0.1'
PORT = 5000

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((HOST, PORT))

username = input("Enter username: ").strip()

# global latency store
latencies = []

# ✅ ensure results folder exists
os.makedirs("results", exist_ok=True)


# ---------------------------
# SEND MESSAGE
# ---------------------------
def send_msg(msg):
    data = msg.encode()
    length = len(data).to_bytes(4, 'big')
    client.sendall(length + data)


# ---------------------------
# RECEIVE MESSAGE
# ---------------------------
def recv_msg():
    try:
        raw_len = client.recv(4)
        if not raw_len:
            return None

        msg_len = int.from_bytes(raw_len, 'big')

        data = b''
        while len(data) < msg_len:
            packet = client.recv(msg_len - len(data))
            if not packet:
                return None
            data += packet

        return data.decode()
    except:
        return None


# ---------------------------
# RECEIVE THREAD (FIXED)
# ---------------------------
def receive_thread():
    while True:
        message = recv_msg()
        if not message:
            break

        if message == "GET_USER":
            send_msg(username)
            continue

        try:
            parts = message.split("|", 2)

            if len(parts) != 3:
                continue

            sender, ts_str, content = parts

            sender = sender.strip()
            content = content.strip()

            # ✅ ONLY count OWN messages
            if sender == username:
                latency = (time.perf_counter() - float(ts_str)) * 1000
                latencies.append(latency)

                if "burst_" in content:
                    print(".", end="", flush=True)
                else:
                    print(f"\n[Latency] {latency:.4f} ms")

            elif sender == "[SERVER]":
                print(f"\n*** {content} ***")

            else:
                print(f"\n{sender}: {content}")

        except:
            pass


# ---------------------------
# RUN TEST (FIXED RESET)
# ---------------------------
def run_test(size, count=10):
    global latencies

    latencies.clear()   # 🔥 IMPORTANT RESET

    print(f"\n[TEST] Sending {count} messages of {size} bytes", end="")

    payload = "X" * size

    for _ in range(count):
        send_msg(f"{username}|{time.perf_counter()}|SIZE_{size}_{payload}")
        time.sleep(0.01)

    timeout = time.time() + 5

    while len(latencies) < count and time.time() < timeout:
        time.sleep(0.05)

    if latencies:
        avg = sum(latencies) / len(latencies)
        print(f"\n✔ Avg latency: {avg:.4f} ms")

        with open("results/tcp_chat.csv", "a", newline="") as f:
            csv.writer(f).writerow(["tcp_chat", size, avg])

    else:
        print(f"\n⚠ No data for size {size}")


# ---------------------------
# WRITE THREAD
# ---------------------------
def write_thread():
    global latencies

    while True:
        msg = input()

        # ---------------- BURST ----------------
        if msg == "/burst":
            print("🚀 BURST STARTED")

            latencies.clear()   # 🔥 RESET BEFORE BURST

            for i in range(50):
                send_msg(f"{username}|{time.perf_counter()}|burst_{i}")
                time.sleep(0.005)

            timeout = time.time() + 5

            while len(latencies) < 50 and time.time() < timeout:
                time.sleep(0.05)

            if latencies:
                avg = sum(latencies) / len(latencies)
                print(f"\n✔ Burst Avg: {avg:.4f} ms")

                with open("results/tcp_chat.csv", "a", newline="") as f:
                    csv.writer(f).writerow(["tcp_chat", "burst", avg])
            else:
                print("\n⚠ No burst data collected")

            continue

        # ---------------- TEST ----------------
        if msg == "/test":
            print("🧪 RUNNING TESTS")

            latencies = []   # full reset

            for size in [32, 256, 1024]:
                run_test(size)

            continue

        # ---------------- NORMAL MESSAGE ----------------
        send_msg(f"{username}|{time.perf_counter()}|{msg}")


# ---------------------------
# START
# ---------------------------
threading.Thread(target=receive_thread, daemon=True).start()
write_thread()