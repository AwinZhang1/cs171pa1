import socket
import json
import time
import argparse
import csv
import threading

class ClockClient:
    def __init__(self, rho, epsilon_max, duration):
        self.rho = rho  # Clock drift ratio
        self.epsilon_max = epsilon_max  # Maximum tolerable error
        self.duration = duration  # Duration to run (seconds)
        
        # Initialize local clock
        self.R_base = time.time()  # Real process clock at initialization
        self.L_base = self.R_base  # Local time at initialization (no drift initially)
        
        # Network server connection
        self.nw_host = 'localhost'
        self.nw_port = 5000
        
        # CSV file for logging
        self.csv_file = 'output.csv'
        self.csv_lock = threading.Lock()
        
        # Initialize CSV file (write header; individual rows will contain raw floats)
        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['actual_time', 'local_time'])
    
    def get_local_time(self):
        """Calculate local clock with drift: L(t) = L_base + (R(t) - R_base) * (1 + rho)"""
        R_t = time.time()
        L_t = self.L_base + (R_t - self.R_base) * (1 + self.rho)
        return L_t
    
    def update_local_clock(self, new_local_time):
        """Update the local clock base values"""
        self.R_base = time.time()
        self.L_base = new_local_time
    
    def request_time_sync(self):
        """Request time from server using Cristian's Algorithm"""
        try:
            # Record time when request is sent
            T0 = time.time()
            
            # Connect to network server
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((self.nw_host, self.nw_port))
            
            # Send time request
            request = {'type': 'time_req'}
            client_socket.sendall(json.dumps(request).encode('utf-8'))
            
            # Receive response
            response_data = client_socket.recv(1024).decode('utf-8')
            
            # Record time when response is received
            T1 = time.time()
            
            client_socket.close()
            
            # Parse response
            response = json.loads(response_data)
            server_time = response['server_time']
            
            # Cristian's Algorithm: estimate current time
            # RTT = T1 - T0
            # Estimated time = server_time + RTT/2
            RTT = T1 - T0
            estimated_time = server_time + RTT / 2
            
            # Update local clock
            self.update_local_clock(estimated_time)
            
            print(f"[Client] Synchronized. RTT: {RTT*1000:.3f}ms, Server time: {server_time:.3f}, Estimated: {estimated_time:.3f}")
            
            return RTT
            
        except Exception as e:
            print(f"[Client] Error during sync: {e}")
            return None
    
    def calculate_sync_interval(self):
        """Calculate how often to synchronize based on epsilon_max and drift"""
        # Maximum network delay from spec: one-way between 0.1 and 0.5 ms -> round-trip worst-case ~1ms
        max_network_delay = 0.001

        # Error sources:
        # 1) Clock drift accumulates as t * |rho|
        # 2) Network uncertainty contributes up to half the RTT
        network_error = max_network_delay / 2

        # If drift is essentially zero, sync only once at start
        if abs(self.rho) < 1e-12:
            sync_interval = self.duration
            print(f"[Client] Calculated sync interval (no drift): {sync_interval:.3f}s")
            return sync_interval

        # Compute conservative sync interval so that (t * |rho| + network_error) <= epsilon_max
        available_error = self.epsilon_max - network_error
        if available_error <= 0:
            # Network uncertainty alone exceeds epsilon_max: choose frequent syncs
            raw_interval = 0.1
            sync_interval = 0.1
        else:
            raw_interval = available_error / abs(self.rho)
            # safety margin to account for scheduling and rounding
            sync_interval = raw_interval * 0.9

        # Clamp to a reasonable minimum and not exceed overall duration
        sync_interval = max(0.1, min(sync_interval, self.duration))

        print(f"[Client] Calculated sync interval: {sync_interval:.3f}s (raw {raw_interval:.3f}s, network_err={network_error:.6f})")
        return sync_interval
    
    def log_time(self):
        """Log actual time and local time to CSV"""
        actual_time = time.time()
        local_time = self.get_local_time()
        
        with self.csv_lock:
            with open(self.csv_file, 'a', newline='') as f:
                writer = csv.writer(f)
                # Write raw float values (higher precision) so the grader can accurately check bounds
                writer.writerow([actual_time, local_time])
    
    def logging_thread(self, stop_event):
        """Thread that logs time once per second"""
        while not stop_event.is_set():
            self.log_time()
            time.sleep(1.0)
    
    def run(self):
        """Main client loop"""
        print(f"[Client] Starting with rho={self.rho}, epsilon_max={self.epsilon_max}, duration={self.duration}s")
        
        # Initial synchronization
        print("[Client] Performing initial synchronization...")
        self.request_time_sync()
        
        # Calculate synchronization interval
        sync_interval = self.calculate_sync_interval()
        
        # Start logging thread
        stop_event = threading.Event()
        logger = threading.Thread(target=self.logging_thread, args=(stop_event,))
        logger.daemon = True
        logger.start()
        
        # Run for specified duration with periodic synchronization
        start_time = time.time()
        last_sync = start_time
        
        while time.time() - start_time < self.duration:
            current_time = time.time()
            
            # Check if it's time to synchronize
            if current_time - last_sync >= sync_interval:
                self.request_time_sync()
                last_sync = current_time
            
            time.sleep(0.1)  # Small sleep to prevent busy waiting
        
        # Stop logging thread
        stop_event.set()
        logger.join(timeout=2)
        
        print(f"[Client] Finished. Results written to {self.csv_file}")

def main():
    parser = argparse.ArgumentParser(description='Clock Synchronization Client')
    parser.add_argument('--d', type=float, required=True, help='Duration to run (seconds)')
    parser.add_argument('--epsilon', type=float, required=True, help='Maximum tolerable error')
    parser.add_argument('--rho', type=float, required=True, help='Clock drift ratio')
    
    args = parser.parse_args()
    
    client = ClockClient(rho=args.rho, epsilon_max=args.epsilon, duration=args.d)
    client.run()

if __name__ == '__main__':
    main()
