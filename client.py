import socket
import json
import time
import argparse
import csv
import threading

NETWORK_HOST = 'localhost'
NETWORK_PORT = 5000

class DriftClock:
    def __init__(self, rho):
        self.rho = rho
        self.R_base = time.monotonic()
        self.L_base = time.time()
        self.lock = threading.Lock()

    def get_local_time(self):
        with self.lock:
            R_t = time.monotonic()
            elapsed = R_t - self.R_base
            return self.L_base + elapsed * (1 + self.rho)

    def set_local_time(self, new_local_time):
        with self.lock:
            self.L_base = new_local_time
            self.R_base = time.monotonic()

class Client:
    def __init__(self, epsilon_max, rho, duration):
        self.epsilon_max = epsilon_max
        self.rho = rho
        self.duration = duration

        self.clock = DriftClock(rho)
        self.running = True

        self.sync_interval = self.calculate_sync_interval()

    
    
    def calculate_sync_interval(self):
        if abs(self.rho) < 1e-10:
            return 5.0

        sync_interval = self.epsilon_max / (2.0 * abs(self.rho))
        min_interval = 0.5
        max_interval = max(10.0, self.duration / 2)
        return max(min_interval, min(sync_interval, max_interval))
    
    def request_time_sync(self):
        try:
            T0 = time.monotonic()

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            sock.connect((NETWORK_HOST, NETWORK_PORT))

            request = {'type': 'time_req'}
            sock.sendall(json.dumps(request).encode('utf-8'))

            response = sock.recv(1024).decode('utf-8')
            T1 = time.monotonic()
            sock.close()

            data = json.loads(response)
            T_server = data.get('server_time')
            RTT = T1 - T0
            estimated_server_time = T_server + RTT / 2

            self.clock.set_local_time(estimated_server_time)
            return True
        except Exception as e:
            print(f"[CLIENT] Sync failed: {e}")
            return False
    
    
    def logging_thread(self, csv_file):
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['actual_time', 'local_time'])

            
            actual_time_start = time.time()
            start_mono = time.monotonic()
            last_logged = 0

            while self.running and (time.monotonic() - start_mono) < self.duration:
                elapsed = int(time.monotonic() - start_mono)
                if elapsed > last_logged:
                    actual_time = actual_time_start + elapsed
                    local_time = self.clock.get_local_time()
                    writer.writerow([f"{actual_time:.3f}", f"{local_time:.3f}"])
                    f.flush()
                    last_logged = elapsed
                time.sleep(0.01)


    
    def sync_thread(self):
        self.request_time_sync()
        sync_count = 1

        start_time = time.monotonic()
        next_sync = start_time + self.sync_interval

        while self.running:
            current_time = time.monotonic()
            if (current_time - start_time) >= self.duration:
                break
            if current_time >= next_sync:
                sync_count += 1
                self.request_time_sync()
                next_sync = start_time + sync_count * self.sync_interval
            time.sleep(min(0.1, max(0, next_sync - current_time)))

    
    def run(self):
        log_thread = threading.Thread(target=self.logging_thread, args=('output.csv',))
        log_thread.start()
        sync_t = threading.Thread(target=self.sync_thread)
        sync_t.start()
        try:
            log_thread.join()
            sync_t.join()
        except KeyboardInterrupt:
            self.running = False

def main():
    parser = argparse.ArgumentParser(description='Clock synchronization client')
    parser.add_argument('--d', type=float, required=True, help='Duration in seconds')
    parser.add_argument('--epsilon', type=float, required=True, help='Maximum tolerable error')
    parser.add_argument('--rho', type=float, required=True, help='Clock drift rate')
    
    args = parser.parse_args()
    
    client = Client(epsilon_max=args.epsilon, rho=args.rho, duration=args.d)
    client.run()

if __name__ == "__main__":
    main()
