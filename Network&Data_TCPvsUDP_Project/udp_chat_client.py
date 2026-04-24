import socket
import threading
import time
import csv
import os

SERVER_ADDR = ('localhost', 12000)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65535)
sock.settimeout(1)

seq = 0
pending = {}
send_times = {}

# test + chat tracking
latencies = []
chat_latencies = []
chat_waiting = {}

os.makedirs("results", exist_ok=True)


# -------------------------
# RECEIVE THREAD
# -------------------------
def receive():
    global pending, send_times

    while True:
        try:
            data, _ = sock.recvfrom(65535)
            msg = data.decode()

            if msg.startswith("ACK"):
                ack_seq = int(msg.split()[1])

                if ack_seq in pending:
                    latency = (time.perf_counter() - send_times[ack_seq]) * 1000
                    latencies.append(latency)

                    # ✅ CHAT LATENCY TRACKING
                    if ack_seq in chat_waiting:
                        chat_latencies.append(latency)
                        del chat_waiting[ack_seq]

                    print(".", end="", flush=True)

                    del pending[ack_seq]
                    del send_times[ack_seq]

            else:
                print("\nReceived:", msg)

        except:
            continue


# -------------------------
# SEND PACKET
# -------------------------
def send_packet(username, content, is_chat=False):
    global seq

    packet = f"{seq}|{username}|{time.perf_counter()}|{content}"

    pending[seq] = packet
    send_times[seq] = time.perf_counter()

    if is_chat:
        chat_waiting[seq] = time.perf_counter()

    sock.sendto(packet.encode(), SERVER_ADDR)

    seq += 1


# -------------------------
# BURST TEST
# -------------------------
def burst_test(username):
    print("🚀 BURST STARTED", end="")

    latencies.clear()

    for i in range(50):
        send_packet(username, f"burst_{i}")
        time.sleep(0.005)

    timeout = time.time() + 5

    while len(latencies) < 50 and time.time() < timeout:
        time.sleep(0.05)

    if latencies:
        avg = sum(latencies) / len(latencies)
        print(f"\n✔ Burst Avg Latency: {avg:.4f} ms")

        with open("results/udp_chat.csv", "a", newline="") as f:
            csv.writer(f).writerow(["udp_chat", "burst", avg])
    else:
        print("\n⚠ Burst failed")


# -------------------------
# SIZE TEST (FIXED 1024 ISSUE)
# -------------------------
def size_test(username):
    sizes = [32, 256, 1024]

    for size in sizes:
        print(f"\n🧪 Testing {size} bytes", end="")

        latencies.clear()

        # safe UDP payload
        payload = ("X" * size)[:900]

        for _ in range(20):
            send_packet(username, f"SIZE_{size}_{payload}")
            time.sleep(0.05)

        timeout = time.time() + 5

        while len(latencies) < 20 and time.time() < timeout:
            time.sleep(0.05)

        if latencies:
            avg = sum(latencies) / len(latencies)
            print(f" → Avg: {avg:.4f} ms")

            with open("results/udp_chat.csv", "a", newline="") as f:
                csv.writer(f).writerow(["udp_chat", size, avg])
        else:
            print(" ⚠ No data for size")


# -------------------------
# CHAT LATENCY REPORT
# -------------------------
def chat_latency_report():
    if chat_latencies:
        avg = sum(chat_latencies) / len(chat_latencies)
        print(f"\n💬 Chat Avg Latency: {avg:.4f} ms")

        with open("results/udp_chat.csv", "a", newline="") as f:
            csv.writer(f).writerow(["udp_chat", "chat_avg", avg])
    else:
        print("\n⚠ No chat latency collected")


# -------------------------
# INPUT LOOP
# -------------------------
def send_loop(username):
    while True:
        msg = input()

        if msg == "/burst":
            burst_test(username)

        elif msg == "/test":
            size_test(username)

        elif msg == "/chatstats":
            chat_latency_report()

        else:
            send_packet(username, msg, is_chat=True)


# -------------------------
# MAIN
# -------------------------
def main():
    username = input("Enter username: ")

    sock.sendto(f"REGISTER {username}".encode(), SERVER_ADDR)

    threading.Thread(target=receive, daemon=True).start()

    send_loop(username)


main()