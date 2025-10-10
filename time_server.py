import socket
import json
import time

def main():
    host = 'localhost'
    port = 5001
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(1)
    
    print(f"[Time Server] Started on {host}:{port}")
    
    while True:
        try:
            conn, addr = server_socket.accept()
            data = conn.recv(1024).decode('utf-8')
            
            if not data:
                conn.close()
                continue
            
            request = json.loads(data)
            
            if request.get('type') == 'time_req':
                # Respond immediately with current time (processing time = 0)
                server_time = time.time()
                response = {
                    'type': 'time_resp',
                    'server_time': server_time
                }
                conn.sendall(json.dumps(response).encode('utf-8'))
                print(f"[Time Server] Responded with time: {server_time:.3f}")
            
            conn.close()
            
        except KeyboardInterrupt:
            print("\n[Time Server] Shutting down...")
            break
        except Exception as e:
            print(f"[Time Server] Error: {e}")
    
    server_socket.close()

if __name__ == '__main__':
    main()
