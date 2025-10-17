import socket
import threading
import time
import random

CLIENT_PORT = 5000
TIME_SERVER_HOST = 'localhost'
TIME_SERVER_PORT = 5001
HOST = 'localhost'

# Delay range in seconds: [0.1ms, 0.5ms] = [0.0001s, 0.0005s]
MIN_DELAY = 0.0001
MAX_DELAY = 0.0005

def add_random_delay():
    """Simulate network delay using uniform distribution"""
    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    time.sleep(delay)
    return delay

def forward_to_time_server(client_data, client_socket):
    """Forward client request to time server with delay"""
    try:
        # Add delay before forwarding to time server
        delay1 = add_random_delay()
        
        # Connect to time server
        ts_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ts_socket.connect((TIME_SERVER_HOST, TIME_SERVER_PORT))
        
        # Forward request
        ts_socket.sendall(client_data)
        
        # Receive response from time server
        response = ts_socket.recv(1024)
        ts_socket.close()
        
        # Add delay before forwarding back to client
        delay2 = add_random_delay()
        
        # Forward response to client
        client_socket.sendall(response)
        
        print(f"[NETWORK] Forwarded message (delays: {delay1*1000:.4f}ms, {delay2*1000:.4f}ms)")
        
    except Exception as e:
        print(f"[NETWORK] Error forwarding: {e}")

def handle_client(conn, addr):
    """Handle individual client connection"""
    try:
        data = conn.recv(1024)
        if data:
            forward_to_time_server(data, conn)
    except Exception as e:
        print(f"[NETWORK] Error handling client: {e}")
    finally:
        conn.close()

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, CLIENT_PORT))
    server_socket.listen(5)
    
    print(f"[NETWORK SERVER] Started on {HOST}:{CLIENT_PORT}")
    print(f"[NETWORK SERVER] Forwarding to Time Server at {TIME_SERVER_HOST}:{TIME_SERVER_PORT}")
    print(f"[NETWORK SERVER] Delay range: [{MIN_DELAY*1000:.1f}ms, {MAX_DELAY*1000:.1f}ms]")
    
    try:
        while True:
            conn, addr = server_socket.accept()
            # Handle each request in a separate thread for concurrency
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.start()
            
    except KeyboardInterrupt:
        print("\n[NETWORK SERVER] Shutting down...")
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()
