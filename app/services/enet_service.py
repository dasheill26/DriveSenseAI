import socket
import time

class ENETService:
    def __init__(self, host="169.254.1.1", port=6801):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.host, self.port))
            return True
        except Exception as e:
            raise Exception(f"ENET connection failed: {e}")

    def send(self, cmd: str):
        if not self.sock:
            self.connect()
        self.sock.send((cmd + "\r").encode())
        time.sleep(0.2)
        return self.sock.recv(4096).decode(errors="ignore")

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None