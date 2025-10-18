import socket
import json
import time
import sys

HOST = 'localhost'
PORT = 5001

def get_current_time():
    return time.time()

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    
    
    try:
        while True:
            conn, addr = server_socket.accept()
            try:
                data = conn.recv(1024).decode('utf-8')
                if data:
                    request = json.loads(data)
                    
                    if request.get('type') == 'time_req':
                        server_time = get_current_time()
                        response = {
                            'type': 'time_resp',
                            'server_time': server_time
                        }
                        conn.sendall(json.dumps(response).encode('utf-8'))
                        
            except Exception as e:
                print(f"[TIME SERVER] Error: {e}")
            finally:
                conn.close()
                
    except KeyboardInterrupt:
        print("\n[TIME SERVER] Shutting down...")
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()

