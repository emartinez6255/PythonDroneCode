import socket
import threading
import os
import hashlib

HOST = '0.0.0.0'
PORT = 6000


def checksum(file):
    sha = hashlib.sha256()
    with open(file, "rb") as f:
        while chunk := f.read(4096):
            sha.update(chunk)
    return sha.hexdigest()


def handle(conn, addr):
    print(f"CONNECTED {addr}")

    try:
        req = conn.recv(1024).decode().strip()
        _, filename, chunk_size = req.split()
        chunk_size = int(chunk_size)

        if not os.path.exists(filename):
            conn.send(b"ERROR\n")
            return

        size = os.path.getsize(filename)
        file_hash = checksum(filename)

        conn.send(f"OK {size} {file_hash}\n".encode())

        with open(filename, "rb") as f:
            while chunk := f.read(chunk_size):
                conn.sendall(chunk)

    except:
        pass

    conn.close()


def start():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen()

    print("TCP FILE SERVER RUNNING")

    while True:
        c, addr = s.accept()
        threading.Thread(target=handle, args=(c, addr), daemon=True).start()


start()