# Run with: mpiexec -n 1 python run_ffconnect_timing.py
import time
import csv
import os

from ffconnect.interface import FastFarmInterface

EXE = r"D:\2_PhD_UBC\Code\FASTv355\FAST.Farm_x64_OMP_v355.exe"
TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo", "time", "Test")

CASES = [
    ("ffconnect.fstf",    2),
    ("ffconnect2x2.fstf", 4),
    ("ffconnect3x2.fstf", 6),
    ("ffconnect4x2.fstf", 8),
    ("ffconnect5x2.fstf", 10),
    ("ffconnect6x2.fstf", 12),
]

results = []

for fstf, n_turbines in CASES:
    fstf_path = os.path.join(TEST_DIR, fstf)
    print(f"Running {fstf} ({n_turbines} turbines) ...", flush=True)
    status = "OK"
    try:
        t0 = time.perf_counter()
        interface = FastFarmInterface.from_file(fstf_path, fast_farm_executable=EXE, per_turbine_flags=True)
        interface.init()
        done = False
        while not done:
            done = interface.step()
        elapsed = time.perf_counter() - t0
    except Exception as e:
        elapsed = time.perf_counter() - t0
        status = f"ERROR: {e}"
    print(f"  -> {elapsed:.2f} s  [{status}]", flush=True)
    results.append({"case": fstf, "turbines": n_turbines, "elapsed_seconds": round(elapsed, 3), "status": status})

print("\n--- FFConnect Timing Summary ---")
print(f"{'Case':<22} {'Turbines':>8} {'Time (s)':>10} {'Status'}")
for r in results:
    print(f"{r['case']:<22} {r['turbines']:>8} {r['elapsed_seconds']:>10.3f}  {r['status']}")

csv_path = os.path.join(TEST_DIR, "ffconnect_timing_results.csv")
with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["case", "turbines", "elapsed_seconds", "status"])
    writer.writeheader()
    writer.writerows(results)

print(f"\nResults saved to: {csv_path}")
