import socket
import threading

HOST = '127.0.0.1'
PORT = 5000

clients = {}


def send_framed_msg(sock, msg):
    data = msg.encode()
    length = len(data).to_bytes(4, 'big')
    sock.sendall(length + data)


def recv_framed_msg(sock):
    try:
        raw_len = sock.recv(4)
        if not raw_len:
            return None

        msg_len = int.from_bytes(raw_len, 'big')
        data = b''

        while len(data) < msg_len:
            packet = sock.recv(msg_len - len(data))
            if not packet:
                return None
            data += packet

        return data.decode()

    except:
        return None


def broadcast(message):
    for client in list(clients.keys()):
        try:
            send_framed_msg(client, message)
        except:
            client.close()
            if client in clients:
                del clients[client]


def handle_client(client_socket):
    send_framed_msg(client_socket, "GET_USER")
    username = recv_framed_msg(client_socket)

    if username:
        username = username.strip()
        clients[client_socket] = username
        print(f"[JOIN] {username}")
        broadcast(f"[SERVER]|0|{username} joined")

    while True:
        message = recv_framed_msg(client_socket)

        if message:
            # ✅ FIX: ALWAYS PRINT EVERYTHING
            print(f"[RECEIVED] {message}")
            broadcast(message)

        else:
            if client_socket in clients:
                user = clients[client_socket]
                print(f"[LEAVE] {user}")
                del clients[client_socket]
                broadcast(f"[SERVER]|0|{user} left")

            client_socket.close()
            break


def start():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server.bind((HOST, PORT))
    server.listen()

    print(f"TCP Chat Server running on {HOST}:{PORT}")

    while True:
        client, addr = server.accept()
        threading.Thread(target=handle_client, args=(client,), daemon=True).start()


if __name__ == "__main__":
    start()