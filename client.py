# client.py
import socket
import json
import argparse
import time
import csv
import math

NW_HOST = "127.0.0.1"
NW_PORT = 5500
# Network delay model (seconds) used by NW server: [DELAY_MIN, DELAY_MAX]
# NW uses delays in [0.0001, 0.0005] seconds (0.1 - 0.5 ms)
DELAY_MIN = 0.0001
DELAY_MAX = 0.0005

class LocalClock:
    def __init__(self, drift_rate):
        self.rho = drift_rate
        self.Rbase = time.time()
        self.Lbase = self.Rbase

    def get_time(self):
        Rnow = time.time()
        return self.Lbase + (Rnow - self.Rbase) * (1 + self.rho)

    def set_time(self, new_time):
        Rnow = time.time()
        self.Lbase = new_time
        self.Rbase = Rnow

def cristian_sync(clock):
    t1 = time.time()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((NW_HOST, NW_PORT))
        s.sendall(json.dumps({"type": "time_req"}).encode())
        resp = s.recv(1024)
    t4 = time.time()

    response = json.loads(resp.decode())
    ts = response["server_time"]
    RTT = t4 - t1
    offset = ts + RTT / 2 - clock.get_time()
    clock.set_time(clock.get_time() + offset)
    return RTT / 2, offset

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--d", type=int, default=10)
    parser.add_argument("--epsilon", type=float, default=0.1)
    parser.add_argument("--rho", type=float, default=1e-6)
    args = parser.parse_args()

    clock = LocalClock(args.rho)
    start_time = time.time()
    duration = args.d
    end_time = start_time + duration
    filename = "output.csv"

    # prepare next-write to align with system clock seconds
    next_write = math.ceil(start_time)

    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        # exact required header
        writer.writerow(["actual_time", "local_time"])

        # run until end_time, writing exactly one row per system-second
        while next_write <= end_time:
            sleep_for = next_write - time.time()
            if sleep_for > 0:
                time.sleep(sleep_for)

            # capture times at the write instant
            actual_time = time.time()
            local_time = clock.get_time()

            # format to 3 decimal places (milliseconds) with no extra spaces
            writer.writerow([f"{actual_time:.3f}", f"{local_time:.3f}"])
            csvfile.flush()

            # compute sync interval T based on epsilon and network uncertainty
            # network_half_uncertainty = max per-direction delay (DELAY_MAX)
            network_half_uncertainty = DELAY_MAX
            epsilon = args.epsilon
            rho = args.rho

            if epsilon <= network_half_uncertainty:
                # cannot satisfy error bound due to network uncertainty alone; sync frequently
                sync_interval = 0.1
            else:
                if rho == 0:
                    # drift-free clock; sync rarely but at least once every 1s by default
                    sync_interval = max(1.0, duration)
                else:
                    sync_interval = (epsilon - network_half_uncertainty) / abs(rho)
                    # bound the interval to a reasonable range
                    sync_interval = max(0.1, min(sync_interval, duration))

            # schedule syncs using a next_sync timestamp (simple alignment to multiples)
            # perform a sync when elapsed crosses a multiple of sync_interval
            elapsed = actual_time - start_time
            if sync_interval > 0 and elapsed >= 0:
                # compute number of full intervals since start
                n_intervals = math.floor(elapsed / sync_interval)
                # if we're within a small window after the interval boundary, sync
                if (elapsed - n_intervals * sync_interval) < 0.05:
                    try:
                        delay, offset = cristian_sync(clock)
                        print(f"[Sync] RTT/2={delay:.6f}s Offset={offset:.6f}s")
                    except Exception as e:
                        print(f"[Sync] error: {e}")

            next_write += 1

if __name__ == "__main__":
    main()
