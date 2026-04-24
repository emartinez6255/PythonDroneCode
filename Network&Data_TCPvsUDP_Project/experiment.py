import csv
import matplotlib.pyplot as plt

# Sample data (replace with real collected data)
message_sizes = [32, 256, 1024]
tcp_latency = [10, 15, 25]
udp_latency = [8, 12, 20]

file_sizes = [100, 1000, 5000]  # KB
tcp_throughput = [500, 700, 900]
udp_throughput = [600, 800, 850]

# Save CSV
with open("results/tcp_file.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Message Size", "TCP Latency", "UDP Latency"])
    for i in range(len(message_sizes)):
        writer.writerow([message_sizes[i], tcp_latency[i], udp_latency[i]])

# Graph 1: Latency
plt.figure()
plt.plot(message_sizes, tcp_latency, marker='o', label="TCP")
plt.plot(message_sizes, udp_latency, marker='o', label="UDP")
plt.xlabel("Message Size (bytes)")
plt.ylabel("Latency (ms)")
plt.title("Message Size vs Latency")
plt.legend()
plt.savefig("results/chat_latency.png")

# Graph 2: Throughput
plt.figure()
plt.plot(file_sizes, tcp_throughput, marker='o', label="TCP")
plt.plot(file_sizes, udp_throughput, marker='o', label="UDP")
plt.xlabel("File Size (KB)")
plt.ylabel("Throughput (KB/s)")
plt.title("File Size vs Throughput")
plt.legend()
plt.savefig("results/file_throughput.png")

print("Graphs and CSV generated.")