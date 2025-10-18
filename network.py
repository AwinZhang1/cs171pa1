import socket
import threading
import time
import random

CLIENT_PORT = 5000
TIME_SERVER_HOST = 'localhost'
TIME_SERVER_PORT = 5001
HOST = 'localhost'

MIN_DELAY = 0.0001
MAX_DELAY = 0.0005

def add_random_delay():
    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    time.sleep(delay)
    return delay

def forward_to_time_server(client_data, client_socket):
    try:
        delay1 = add_random_delay()
        ts_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ts_socket.connect((TIME_SERVER_HOST, TIME_SERVER_PORT))
        ts_socket.sendall(client_data)
        response = ts_socket.recv(1024)
        ts_socket.close()
        delay2 = add_random_delay()
        client_socket.sendall(response)
    except Exception:
        pass

def handle_client(conn, _addr):
    try:
        data = conn.recv(1024)
        if data:
            forward_to_time_server(data, conn)
    finally:
        conn.close()

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, CLIENT_PORT))
    server_socket.listen(5)
    try:
        while True:
            conn, addr = server_socket.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.start()
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()
