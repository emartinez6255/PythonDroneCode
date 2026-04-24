import socket
import hashlib
import time
import csv
import os

SERVER_ADDR = ('localhost', 13000)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(5.0)

os.makedirs("results", exist_ok=True)

print("UDP File Transfer Client")

while True:

    filename = input("\nEnter filename (or quit): ").strip()

    if filename.lower() == "quit":
        break

    received = {}
    start_time = None
    end_time = None

    # ✅ FIX: send ONLY filename (no folder)
    sock.sendto(filename.encode(), SERVER_ADDR)

    try:
        while True:
            data, _ = sock.recvfrom(8192)

            if start_time is None:
                start_time = time.perf_counter()

            parts = data.split(b'|', 2)
            if len(parts) < 3:
                continue

            seq = int(parts[0])
            total = int(parts[1])
            payload = parts[2]

            received[seq] = payload

            sock.sendto(f"ACK {seq}".encode(), SERVER_ADDR)

            if len(received) == total:
                end_time = time.perf_counter()
                break

        duration = end_time - start_time
        if duration <= 0:
            duration = 0.000001

        file_data = b''.join(received[i] for i in sorted(received.keys()))

        save_name = "received_" + filename
        with open(save_name, "wb") as f:
            f.write(file_data)

        throughput = (len(file_data) / duration) / 1024
        checksum = hashlib.md5(file_data).hexdigest()

        print("\n--- UDP FILE RESULT ---")
        print(f"Time: {duration:.6f}s")
        print(f"Throughput: {throughput:.2f} KB/s")
        print(f"Checksum: {checksum}")

        with open("results/udp_file.csv", "a", newline="") as f:
            csv.writer(f).writerow([
                "udp_file",
                filename,
                len(file_data),
                round(duration, 6),
                round(throughput, 2)
            ])

    except socket.timeout:
        print("Timeout / file not found")