import socket
import json
import time
import math
import argparse
import csv
import threading
import os

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
        
        # Buffer for log entries to decouple timing from I/O
        self.log_buffer = []
        self.buffer_lock = threading.Lock()
        
        # Track measured RTT for adaptive sync interval
        self.measured_rtt = None
        
        # Remove old CSV file if it exists to avoid confusion
        if os.path.exists(self.csv_file):
            os.remove(self.csv_file)
        
        # Open CSV file once and keep writer alive to reduce per-write overhead
        # We removed any old file above, so write header now and keep file open
        self.csv_f = open(self.csv_file, 'a', newline='')
        self.csv_writer = csv.writer(self.csv_f)
        self.csv_writer.writerow(['actual_time', 'local_time'])
        # Ensure header is persisted
        self.csv_f.flush()
        try:
            os.fsync(self.csv_f.fileno())
        except Exception:
            # os.fsync may not be supported on some platforms; ignore if it fails
            pass
    
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
            # Record time when request is sent (using REAL clock for RTT measurement)
            T0 = time.time()
            
            # Connect to network server
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((self.nw_host, self.nw_port))
            
            # Send time request
            request = {'type': 'time_req'}
            client_socket.sendall(json.dumps(request).encode('utf-8'))
            
            # Receive response
            response_data = client_socket.recv(1024).decode('utf-8')
            
            # Record time when response is received (using REAL clock for RTT measurement)
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
            
            # Store measured RTT for adaptive interval calculation
            self.measured_rtt = RTT
            
            # Update local clock
            self.update_local_clock(estimated_time)
            
            print(f"[Client] Synchronized. RTT: {RTT*1000:.3f}ms, Server time: {server_time:.3f}, Estimated: {estimated_time:.3f}")
            
            return RTT
            
        except Exception as e:
            print(f"[Client] Error during sync: {e}")
            return None
    
    def calculate_sync_interval(self):
        """
        Calculate how often to synchronize based on epsilon_max and drift.
        This is computed ONCE based on the drift model, accounting for both
        network error and clock drift error.
        """
        # Use measured RTT if available, otherwise use worst-case estimate
        if self.measured_rtt is not None:
            # Use measured RTT with a safety margin (1.5x to account for variance)
            max_network_delay = self.measured_rtt * 1.5
        else:
            # Worst-case: both delays at 0.5ms = 1ms RTT
            max_network_delay = 0.001
        
        # Network uncertainty contributes up to half the RTT (one-way delay estimate)
        network_error = max_network_delay / 2
        
        # If drift is essentially zero, sync only once at start
        if abs(self.rho) < 1e-12:
            sync_interval = self.duration
            print(f"[Client] Calculated sync interval (no drift): {sync_interval:.3f}s")
            return sync_interval
        
        # Compute sync interval so that (t * |rho| + network_error) <= epsilon_max
        # Solve for t: t <= (epsilon_max - network_error) / |rho|
        available_error = self.epsilon_max - network_error
        
        if available_error <= 0:
            # Network uncertainty alone exceeds epsilon_max: need very frequent syncs
            sync_interval = 0.1
            print(f"[Client] Warning: Network error ({network_error:.6f}s) >= epsilon_max ({self.epsilon_max:.6f}s)")
        else:
            raw_interval = available_error / abs(self.rho)
            # Apply safety margin (80% of theoretical interval) to account for:
            # - Scheduling delays
            # - RTT variance
            # - Drift accumulation between measurements
            sync_interval = raw_interval * 0.8
        
        # Clamp to reasonable bounds
        sync_interval = max(0.1, min(sync_interval, self.duration))
        
        print(f"[Client] Calculated sync interval: {sync_interval:.3f}s (network_err={network_error*1000:.3f}ms, available_err={available_error*1000:.3f}ms)")
        return sync_interval
    
    def log_time(self):
        """Capture actual time and local time (buffered for performance)"""
        actual_time = time.time()
        local_time = self.get_local_time()
        
        # Add to buffer instead of writing immediately
        with self.buffer_lock:
            self.log_buffer.append((actual_time, local_time))
    
    def flush_logs(self):
        """Write buffered logs to CSV file"""
        with self.buffer_lock:
            if not self.log_buffer:
                return
            
            entries = self.log_buffer.copy()
            self.log_buffer.clear()
        
        # Write to file without holding the buffer lock
        with self.csv_lock:
            for actual_time, local_time in entries:
                # Use the persistent writer and flush after every write to minimize
                # the chance that a delayed write will cause a multi-second gap.
                self.csv_writer.writerow([f"{actual_time:.3f}", f"{local_time:.3f}"])
            # Flush Python buffers
            try:
                self.csv_f.flush()
            except Exception:
                pass
            # Ask OS to flush to disk as well (may be a no-op / raise on some platforms)
            try:
                os.fsync(self.csv_f.fileno())
            except Exception:
                pass
    
    def logging_thread(self, stop_event):
        """Thread that logs time once per second, never skipping seconds"""
        # Use monotonic clock for scheduling to avoid wall-clock jumps
        mono_start = time.monotonic()
        # Align to next whole second boundary relative to wall-clock, but schedule with monotonic offsets
        wall_start = time.time()
        aligned_wall_start = math.ceil(wall_start)
        # compute how many seconds until that aligned wall clock
        initial_wait_wall = aligned_wall_start - wall_start
        # But use monotonic to wait the same amount
        if initial_wait_wall > 0:
            target_mono = mono_start + initial_wait_wall
        else:
            target_mono = mono_start

        expected_log_count = 0

        # We'll flush/fsync less frequently to avoid blocking; count rows since last fsync
        fsync_counter = 0
        FSYNC_EVERY = 5

        while not stop_event.is_set():
            # Calculate monotonic target for the next log
            next_target_mono = target_mono + expected_log_count

            # Sleep until very near the next target
            while True:
                now_mono = time.monotonic()
                remaining = next_target_mono - now_mono
                if remaining <= 0:
                    break
                # Sleep in coarse chunks then fine-grained
                if remaining > 0.1:
                    time.sleep(0.05)
                elif remaining > 0.01:
                    time.sleep(0.005)
                else:
                    # busy-wait small fraction to improve precision
                    time.sleep(remaining * 0.5)
                if stop_event.is_set():
                    break

            if stop_event.is_set():
                break

            # One log tick (may need to catch up if behind)
            self.log_time()
            expected_log_count += 1

            # If we're behind more than 1, catch up immediately
            # based on wall-clock (keeps actual_time aligned with wall clock boundaries)
            wall_now = time.time()
            should_have_logged = int(wall_now - aligned_wall_start) + 1
            while expected_log_count < should_have_logged and not stop_event.is_set():
                self.log_time()
                expected_log_count += 1

            # After producing entries, flush them here (avoids separate flusher thread)
            with self.csv_lock:
                # Move buffered entries to local list and write using persistent writer
                with self.buffer_lock:
                    entries = self.log_buffer.copy()
                    self.log_buffer.clear()

                for actual_time, local_time in entries:
                    self.csv_writer.writerow([f"{actual_time:.3f}", f"{local_time:.3f}"])
                    fsync_counter += 1

                try:
                    self.csv_f.flush()
                except Exception:
                    pass
                if fsync_counter >= FSYNC_EVERY:
                    try:
                        os.fsync(self.csv_f.fileno())
                    except Exception:
                        pass
                    fsync_counter = 0
    
    def run(self):
        """Main client loop"""
        print(f"[Client] Starting with rho={self.rho}, epsilon_max={self.epsilon_max}, duration={self.duration}s")
        
        # Start logging thread FIRST so it doesn't miss the initial second
        stop_event = threading.Event()
        logger = threading.Thread(target=self.logging_thread, args=(stop_event,))
        logger.daemon = True
        logger.start()
        
        # Start a periodic flusher thread to write buffered logs
        def flush_periodically():
            while not stop_event.is_set():
                time.sleep(0.5)  # Flush twice per second
                self.flush_logs()
        
        flusher = threading.Thread(target=flush_periodically)
        flusher.daemon = True
        flusher.start()
        
        # Store the REAL start time for duration checking
        real_start_time = time.time()
        
        # Initial synchronization
        print("[Client] Performing initial synchronization...")
        self.request_time_sync()
        
        # Calculate synchronization interval based on drift model ONLY
        sync_interval = self.calculate_sync_interval()
        
        # Record LOCAL time of last sync (this is key!)
        last_sync_local_time = self.get_local_time()
        
        # Run for specified duration with periodic synchronization
        # Note: We check duration against REAL time (to know when to stop the program)
        # but resync decisions are based on LOCAL time
        while time.time() - real_start_time < self.duration:
            current_local_time = self.get_local_time()
            
            # Check if it's time to synchronize using LOCAL clock
            # This is the key fix: use local_time - last_sync_local_time, not real time!
            if current_local_time - last_sync_local_time >= sync_interval:
                # Run sync in main thread - but logging thread runs independently
                self.request_time_sync()
                last_sync_local_time = self.get_local_time()  # Update based on LOCAL time
                
                # Optionally recalculate interval with updated RTT measurement
                new_interval = self.calculate_sync_interval()
                if abs(new_interval - sync_interval) > 0.1:
                    print(f"[Client] Adjusting sync interval: {sync_interval:.3f}s -> {new_interval:.3f}s")
                    sync_interval = new_interval
            
            time.sleep(0.1)  # Small sleep to prevent busy waiting
        
        # Stop logging thread and wait for it to finish
        stop_event.set()
        logger.join(timeout=2)
        flusher.join(timeout=1)
        
        # Final flush to ensure all logs are written
        self.flush_logs()
        # Close persistent CSV file
        try:
            self.csv_f.close()
        except Exception:
            pass
        
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
