//Project Structure
Network&Data_TCPvsUDP_Project/
│
├── tcp_chat_client.py
├── tcp_chat_server.py
├── tcp_file_client.py
├── tcp_file_server.py
│
├── udp_chat_client.py
├── udp_chat_server.py
├── udp_file_client.py
├── udp_file_server.py
│
├── plot_tcp_udp_comparison.py
│
├── results/
│   ├── tcp_chat.csv
│   ├── udp_chat.csv
│   ├── tcp_file.csv
│   ├── udp_file.csv
│   ├── chat_comparison.png
│   ├── file_comparison.png
│
└── test files:
    ├── test.txt
    ├── test_100kb.dat
    ├── test_1mb.dat
    ├── test_5mb.dat

//Requirements
pip install matplotlib

// Hwo to Run 
!!!!You MUST start servers before clients!!!!
1. Start Severs
//TCP Servers
python tcp_chat_server.py
python tcp_file_server.py
//UDP Servers
python udp_chat_server.py
python udp_file_server.py

2. Run TCP Test
python tcp_chat_client.py
-----Commands Inside-----
/burst
/test
hello
//File Client
python tcp_file_client.py
-----Test Files-----
test.txt
test_100kb.dat
test_1mb.dat
test_5mb.dat

3. Run UDP Tests
//Chat Client
python udp_chat_client.py
-----Commands-----
/burst
/test
hello
//File Client
python udp_file_client.py
-----Test Files-----
test_100kb.dat
test_1mb.dat
test_5mb.dat

4. Generate Graphs
python plot_tcp_udp_comparison.py
//This will generate two different graphs. Once for chat comparison and one for file comparison
-----Example-----
results/chat_comparison.png
results/file_comparison.png

_____________Output Files__________________
//Chat Results
tcp_chat.csv
udp_chat.csv

//File Results
tcp_file.csv
udp_file.csv

//Graphs
chat_comparison.png
file_comparison.png

---------------Purpose of Project-------------------
//Chat System
Message latency
Burst performance (50 packets)
Small vs Medium vs Large message sizes

//File System
Transfer time
Throughput (KB/s)
Reliability under UDP vs TCP

---------------Key Observatuions--------------------
TCP: more stable, slightly higher latency
UDP: faster, but less reliable (may lose packets)
Larger messages increase latency differences

--------------Key Notes-----------------------------
Always run servers first
Do no close server terminals during tests
Clear /results folder if rerunning experiments
Run multiple test cycles for better accuracy

--------------Troubleshooting-----------------------
❌ “Timeout / file not found”
Server not running
Wrong filename
❌ No CSV generated
/results folder missing
client not completing test properly
❌ Graph missing file data
CSV not generated or empty


------------------Author---------------------------
Networks System Performance Project
TCP vs UDP Analysis using Python sockets
Eduardo A. Martinez