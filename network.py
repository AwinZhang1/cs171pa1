import socket
import json
import time
import random
import threading

def handle_client_to_server(data, client_conn):
    """Forward message from client to time server with delay"""
    try:
        # Add random delay (0.1 to 0.5 ms)
        delay = random.uniform(0.0001, 0.0005)  # Convert ms to seconds
        time.sleep(delay)
        
        # Forward to time server
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect(('localhost', 5001))
        server_socket.sendall(data.encode('utf-8'))
        
        # Receive response from time server
        response = server_socket.recv(1024)
        server_socket.close()
        
        # Add random delay for return path
        delay = random.uniform(0.0001, 0.0005)
        time.sleep(delay)
        
        # Forward response back to client
        client_conn.sendall(response)
        
        print(f"[Network Server] Message forwarded with delays")
        
    except Exception as e:
        print(f"[Network Server] Error: {e}")

def main():
    host = 'localhost'
    port = 5000
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)
    
    print(f"[Network Server] Started on {host}:{port}")
    
    while True:
        try:
            conn, addr = server_socket.accept()
            data = conn.recv(1024).decode('utf-8')
            
            if not data:
                conn.close()
                continue
            
            # Handle in separate thread to allow concurrent requests
            thread = threading.Thread(target=handle_client_to_server, args=(data, conn))
            thread.start()
            
        except KeyboardInterrupt:
            print("\n[Network Server] Shutting down...")
            break
        except Exception as e:
            print(f"[Network Server] Error: {e}")
    
    server_socket.close()

if __name__ == '__main__':
    main()
