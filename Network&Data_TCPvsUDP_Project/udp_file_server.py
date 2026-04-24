import socket
import os

SERVER_ADDR = ('localhost', 13000)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(SERVER_ADDR)

print("UDP File Server running...")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

while True:
    try:
        data, addr = sock.recvfrom(1024)
        filename = data.decode().strip()

        # ✅ FIX: look in SAME folder only
        full_path = os.path.join(BASE_DIR, filename)

        print(f"[REQUEST] {filename} from {addr}")

        if not os.path.exists(full_path):
            print(f"[ERROR] File not found: {filename}")
            sock.sendto(b"ERROR", addr)
            continue

        chunk_size = 4096
        filesize = os.path.getsize(full_path)
        total_packets = (filesize // chunk_size) + (filesize % chunk_size > 0)

        with open(full_path, "rb") as f:
            for seq in range(total_packets):
                payload = f.read(chunk_size)

                packet = f"{seq}|{total_packets}|".encode() + payload

                while True:
                    sock.sendto(packet, addr)
                    sock.settimeout(1.0)

                    try:
                        ack, _ = sock.recvfrom(1024)
                        if ack.decode() == f"ACK {seq}":
                            break
                    except socket.timeout:
                        continue

        sock.settimeout(None)
        print(f"[DONE] {filename}")

    except Exception as e:
        print("Server error:", e)
        sock.settimeout(None)