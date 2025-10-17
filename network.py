import socket
import json
import time
import argparse
import csv
import threading
import sys

NETWORK_HOST = 'localhost'
NETWORK_PORT = 5000

class DriftClock:
    """Simulates a clock with drift"""
    def __init__(self, rho):
        self.rho = rho  # Drift rate
        self.R_base = time.monotonic()  # Real monotonic clock when last set
        # Initialize with current wall time from time.time()
        self.L_base = time.time()  # Local clock value when last set
        self.lock = threading.Lock()
        print(f"[CLOCK] Initialized at L_base={self.L_base:.3f}, R_base={self.R_base:.3f}")
        
    def get_local_time(self):
        """Get current local time with drift: L(t) = L_base + (R(t) - R_base) * (1 + rho)"""
        with self.lock:
            R_t = time.monotonic()
            elapsed = R_t - self.R_base
            L_t = self.L_base + elapsed * (1 + self.rho)
            return L_t
    
    def set_local_time(self, new_local_time):
        """Update the local clock to a new value"""
        with self.lock:
            old_L = self.L_base
            self.L_base = new_local_time
            self.R_base = time.monotonic()
            print(f"[CLOCK] Synced: {old_L:.3f} -> {new_local_time:.3f} (Δ={new_local_time-old_L:.3f}s)")

class Client:
    def __init__(self, epsilon_max, rho, duration):
        self.epsilon_max = epsilon_max
        self.rho = rho
        self.duration = duration
        
        # Initialize actual_time baseline
        # This represents a "perfect" clock synchronized with the server
        self.actual_time_base = time.time()
        self.actual_time_mono_base = time.monotonic()
        self.actual_time_lock = threading.Lock()
        
        self.clock = DriftClock(rho)
        self.running = True
        
        # Calculate synchronization interval
        self.sync_interval = self.calculate_sync_interval()
        
        print(f"[CLIENT] Initialized")
        print(f"[CLIENT] Max error: {epsilon_max}s, Drift rate: {rho}")
        print(f"[CLIENT] Sync interval: {self.sync_interval:.3f}s")
    
    
    def update_actual_time_base(self, server_time):
        """Update actual time baseline when synchronizing with server"""
        with self.actual_time_lock:
            self.actual_time_base = server_time
            self.actual_time_mono_base = time.monotonic()
        
    def calculate_sync_interval(self):
        """
        Calculate how often to sync based on max tolerable error.
        
        After sync, drift error grows as: |ρ × t|
        We need: |ρ × t| ≤ ε_max
        Therefore: t ≤ ε_max / |ρ|
        
        Using safety factor of 2 to account for network delays:
        sync_interval = ε_max / (2|ρ|)
        """
        if abs(self.rho) < 1e-10:
            # No drift, sync every 5 seconds for network uncertainty
            return 5.0
        
        # Sync interval with safety factor of 2
        sync_interval = self.epsilon_max / (2.0 * abs(self.rho))
        
        # Reasonable bounds: at least 0.5s, at most half the duration
        min_interval = 0.5
        max_interval = max(10.0, self.duration / 2)
        
        sync_interval = max(min_interval, min(sync_interval, max_interval))
        
        return sync_interval
    
    def request_time_sync(self):
        """Request time from server via network using Cristian's Algorithm"""
        try:
            # Record time when request is sent
            T0 = time.monotonic()
            
            # Connect to network server
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((NETWORK_HOST, NETWORK_PORT))
            
            # Send request
            request = {'type': 'time_req'}
            sock.sendall(json.dumps(request).encode('utf-8'))
            
            # Receive response
            response = sock.recv(1024).decode('utf-8')
            T1 = time.monotonic()  # Record time when response received
            
            sock.close()
            
            # Parse response
            data = json.loads(response)
            T_server = data['server_time']
            
            # Cristian's Algorithm: estimate current server time
            RTT = T1 - T0
            estimated_server_time = T_server + RTT / 2
            
            # Update both the drifting local clock AND the perfect actual_time baseline
            self.clock.set_local_time(estimated_server_time)
            self.update_actual_time_base(estimated_server_time)
            
            print(f"[CLIENT] Synced. RTT: {RTT*1000:.3f}ms, Server time: {T_server:.3f}")
            
            return True
            
        except Exception as e:
            print(f"[CLIENT] Sync failed: {e}")
            return False
    
    def logging_thread(self, csv_file):
        """Thread to log actual_time and local_time once per second"""
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['actual_time', 'local_time'])

            start_wall = time.time()
            start_mono = time.monotonic()
            last_logged = 0

            while self.running and (time.monotonic() - start_mono) < self.duration:
                elapsed = int(time.monotonic() - start_mono)
                if elapsed > last_logged:  # only once per second
                    actual_time = start_wall + elapsed  # keeps consistent epoch-based increment
                    local_time = self.clock.get_local_time()

                    writer.writerow([f"{actual_time:.3f}", f"{local_time:.3f}"])
                    f.flush()

                    last_logged = elapsed

                time.sleep(0.01)

        print(f"[CLIENT] Logging complete. Results saved to {csv_file}")

    
    def sync_thread(self):
        """Thread to periodically sync with time server"""
        print(f"[CLIENT] Performing initial sync...")
        self.request_time_sync()
        sync_count = 1

        start_time = time.monotonic()
        next_sync = start_time + self.sync_interval

        while self.running:
            current_time = time.monotonic()

            # stop if duration elapsed
            if (current_time - start_time) >= self.duration:
                break

            if current_time >= next_sync:
                sync_count += 1
                print(f"[CLIENT] Performing sync #{sync_count} (interval: {self.sync_interval:.2f}s)")
                self.request_time_sync()
                # keep sync schedule stable
                next_sync = start_time + sync_count * self.sync_interval

            time.sleep(min(0.1, max(0, next_sync - current_time)))

        print(f"[CLIENT] Total syncs performed: {sync_count}")

    
    def run(self):
        """Run the client"""
        print(f"[CLIENT] Starting for {self.duration}s...")
        
        # Start logging thread
        log_thread = threading.Thread(target=self.logging_thread, args=('output.csv',))
        log_thread.start()
        
        # Start sync thread
        sync_t = threading.Thread(target=self.sync_thread)
        sync_t.start()
        
        # Wait for completion
        try:
            log_thread.join()
            sync_t.join()
        except KeyboardInterrupt:
            print("\n[CLIENT] Interrupted")
            self.running = False
        
        print("[CLIENT] Finished")

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
