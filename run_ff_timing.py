import subprocess
import time
import csv
import os

EXE = r"D:\2_PhD_UBC\Code\FASTv355\FAST.Farm_x64_OMP_v355.exe"
TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo", "time", "Test")

CASES = [
    ("ff.fstf",    2),
    ("ff2x2.fstf", 4),
    ("ff3x2.fstf", 6),
    ("ff4x2.fstf", 8),
    ("ff5x2.fstf", 10),
    ("ff6x2.fstf", 12),
]

results = []

for fstf, n_turbines in CASES:
    print(f"Running {fstf} ({n_turbines} turbines) ...", flush=True)
    t0 = time.perf_counter()
    proc = subprocess.run([EXE, fstf], cwd=TEST_DIR)
    elapsed = time.perf_counter() - t0
    status = "OK" if proc.returncode == 0 else f"ERROR (rc={proc.returncode})"
    print(f"  -> {elapsed:.2f} s  [{status}]", flush=True)
    results.append({"case": fstf, "turbines": n_turbines, "elapsed_seconds": round(elapsed, 3), "status": status})

print("\n--- FF Timing Summary ---")
print(f"{'Case':<18} {'Turbines':>8} {'Time (s)':>10} {'Status'}")
for r in results:
    print(f"{r['case']:<18} {r['turbines']:>8} {r['elapsed_seconds']:>10.3f}  {r['status']}")

csv_path = os.path.join(TEST_DIR, "ff_timing_results.csv")
with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["case", "turbines", "elapsed_seconds", "status"])
    writer.writeheader()
    writer.writerows(results)

print(f"\nResults saved to: {csv_path}")
