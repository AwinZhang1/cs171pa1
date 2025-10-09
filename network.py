# network.py
import socket
import json
import random
import time
import threading
import errno

CLIENT_PORT = 5000
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 6000
NW_HOST = "127.0.0.1"
NW_PORT = 5500

def handle_client(conn):
    try:
        data = conn.recv(1024)
        if not data:
            conn.close()
            return

        # Add random network delay (client->server)
        delay = random.uniform(0.0001, 0.0005)
        time.sleep(delay)

        # Forward to time server (with error handling)
        response = None
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                s.connect((SERVER_HOST, SERVER_PORT))
                s.sendall(data)
                response = s.recv(1024)
        except Exception as e:
            print(f"[NW] error forwarding to time server: {e}")

        # Add another random delay before returning (server->client)
        delay = random.uniform(0.0001, 0.0005)
        time.sleep(delay)

        if response:
            try:
                conn.sendall(response)
            except Exception as e:
                print(f"[NW] failed to send response to client: {e}")
    except Exception as e:
        print(f"[NW] unexpected error handling client: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass

def run_network_server():
    # create, set reuseaddr, and attempt to bind with a few retries if address is busy
    s = None
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((NW_HOST, NW_PORT))
            s.listen(5)
            print(f"[NW Server] Listening on {NW_HOST}:{NW_PORT}")
            break
        except OSError as e:
            if e.errno == errno.EADDRINUSE and attempt < max_attempts:
                print(f"[NW] Address in use, retrying ({attempt}/{max_attempts})...")
                time.sleep(0.5)
                continue
            else:
                print(f"[NW] Failed to bind {NW_HOST}:{NW_PORT}: {e}")
                raise

    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn,)).start()

if __name__ == "__main__":
    run_network_server()
