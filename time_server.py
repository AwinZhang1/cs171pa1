# time_server.py
import socket
import json
import time
import errno

HOST = "127.0.0.1"
PORT = 6000

def run_time_server():
    # create, set reuseaddr, and attempt to bind with a few retries if address is busy
    server_socket = None
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((HOST, PORT))
            server_socket.listen(1)
            print(f"[Time Server] Listening on {HOST}:{PORT}")
            break
        except OSError as e:
            if e.errno == errno.EADDRINUSE and attempt < max_attempts:
                print(f"[Time Server] Address in use, retrying ({attempt}/{max_attempts})...")
                time.sleep(0.5)
                continue
            else:
                print(f"[Time Server] Failed to bind {HOST}:{PORT}: {e}")
                raise

    while True:
        conn, addr = server_socket.accept()
        data = conn.recv(1024)
        if not data:
            conn.close()
            continue
        # be defensive: ignore malformed JSON instead of crashing
        try:
            message = json.loads(data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"[Time Server] received invalid data from {addr}: {e}")
            conn.close()
            continue

        if message.get("type") == "time_req":
            response = {"type": "time_resp", "server_time": time.time()}
            try:
                conn.sendall(json.dumps(response).encode())
            except Exception as e:
                print(f"[Time Server] failed to send response to {addr}: {e}")
        else:
            # unknown message type; ignore
            print(f"[Time Server] unknown message type from {addr}: {message.get('type')}")
        conn.close()

if __name__ == "__main__":
    run_time_server()
