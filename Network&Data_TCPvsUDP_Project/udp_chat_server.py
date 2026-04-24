import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', 12000))

clients = {}
received = set()

print("UDP Chat Server running...")

while True:
    data, addr = sock.recvfrom(1024)
    msg = data.decode()

    if msg.startswith("REGISTER"):
        username = msg.split()[1]
        clients[addr] = username
        print(f"{username} joined")
        continue

    seq, content = msg.split("|", 1)
    seq = int(seq)

    sock.sendto(f"ACK {seq}".encode(), addr)

    if (addr, seq) in received:
        continue

    received.add((addr, seq))

    print(content)

    for client in list(clients.keys()):
        if client != addr:
            sock.sendto(content.encode(), client)