import socket
import time
import hashlib
import csv
import os

HOST = '127.0.0.1'
PORT = 6000

os.makedirs("results", exist_ok=True)


# ---------------- CHECKSUM ----------------
def checksum(file):
    sha = hashlib.sha256()
    with open(file, "rb") as f:
        while chunk := f.read(4096):
            sha.update(chunk)
    return sha.hexdigest()


# ---------------- RECEIVE FILE ----------------
def receive_file(filename, chunk_size):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((HOST, PORT))

    client.send(f"GET {filename} {chunk_size}\n".encode())

    header = client.recv(1024).decode().strip()

    if header.startswith("ERROR"):
        print("❌ File not found on server")
        client.close()
        return

    _, filesize, server_hash = header.split()
    filesize = int(filesize)

    received = 0
    start = time.perf_counter()

    with open("received_" + filename, "wb") as f:
        while received < filesize:
            data = client.recv(chunk_size)
            if not data:
                break
            f.write(data)
            received += len(data)
            print(f"\rProgress: {(received/filesize)*100:.2f}%", end="")

    end = time.perf_counter()

    duration = end - start
    if duration <= 0:
        duration = 0.000001

    throughput = (filesize / 1024) / duration

    print(f"\nTime: {duration:.6f}s")
    print(f"Throughput: {throughput:.4f} KB/s")

    if checksum("received_" + filename) == server_hash:
        print("Checksum: MATCH")
    else:
        print("Checksum: FAIL")

    # ✅ WRITE TO CORRECT FILE
    with open("results/tcp_file.csv", "a", newline="") as f:
        csv.writer(f).writerow([
            "tcp_file",
            filesize,
            chunk_size,
            round(throughput, 4)
        ])

    client.close()


# ---------------- TEST MODE ----------------
def run_tests(filename):
    chunk_sizes = [1024, 4096, 16384]

    print("\n=== FILE TEST START ===\n")

    for chunk in chunk_sizes:
        print(f"\n--- Testing chunk size: {chunk} ---")
        receive_file(filename, chunk)
        print(f"[DONE] chunk={chunk}")

    print("\n=== FILE TEST COMPLETE ===\n")


# ---------------- MAIN (CRITICAL FIX) ----------------
if __name__ == "__main__":
    print("=== TCP FILE CLIENT STARTED ===")

    filename = input("Filename: ").strip()

    if not filename:
        print("No filename provided. Exiting.")
        exit()

    mode = input("Enter 1 (single test) or 2 (full test): ").strip()

    if mode == "1":
        chunk = int(input("Chunk size (1024 / 4096 / 16384): ").strip())
        receive_file(filename, chunk)

    elif mode == "2":
        run_tests(filename)

    else:
        print("Invalid mode selected. Exiting.")