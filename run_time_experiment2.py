# Run with: mpiexec -n 1 python run_time_experiment2.py
"""
Timing experiment: compare wall-clock runtime of direct FAST.Farm (ff) vs
the Python ffconnect interface (ffconnect) across turbine counts 2..12,
using the test cases in demo/time/Test. No control is applied in either case.
Results are saved to results/turbine_scaling_timing.csv.
"""

import csv
import subprocess
import time
from pathlib import Path

from ffconnect.interface import FastFarmInterface

# ============================================================
# Paths
# ============================================================
FF_EXE_OMP = r"D:\2_PhD_UBC\Code\FASTv355\FAST.Farm_x64_OMP_v355.exe"
TEST_DIR   = Path(__file__).resolve().parent / "demo" / "time" / "Test"
OUT_CSV    = Path(__file__).resolve().parent / "results" / "turbine_scaling_timing.csv"

CASES = [
    (2,  "ff.fstf",     "ffconnect.fstf"),
    (4,  "ff2x2.fstf",  "ffconnect2x2.fstf"),
    (6,  "ff3x2.fstf",  "ffconnect3x2.fstf"),
    (8,  "ff4x2.fstf",  "ffconnect4x2.fstf"),
    (10, "ff5x2.fstf",  "ffconnect5x2.fstf"),
    (12, "ff6x2.fstf",  "ffconnect6x2.fstf"),
]


# ============================================================
# Helpers
# ============================================================

def run_ff(fstf_name: str):
    """Run direct FAST.Farm for the given case; return (elapsed_seconds, status)."""
    t0 = time.perf_counter()
    proc = subprocess.run([FF_EXE_OMP, fstf_name], cwd=str(TEST_DIR))
    elapsed = time.perf_counter() - t0
    status = "OK" if proc.returncode == 0 else f"ERROR (rc={proc.returncode})"
    return elapsed, status


def run_ffconnect(fstf_path: Path):
    """Run ffconnect interface (no control) for the given case; return (elapsed_seconds, status)."""
    status = "OK"
    t0 = time.perf_counter()
    try:
        interface = FastFarmInterface.from_file(
            str(fstf_path), fast_farm_executable=FF_EXE_OMP, per_turbine_flags=True
        )
        interface.init()
        done = False
        while not done:
            done = interface.step()
        elapsed = time.perf_counter() - t0
    except Exception as e:
        elapsed = time.perf_counter() - t0
        status = f"ERROR: {e}"
    return elapsed, status


# ============================================================
# Experiment
# ============================================================

OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

rows = []
for turbines, ff_fstf, ffc_fstf in CASES:
    print(f"\n=== {turbines} turbines ===")

    print(f"  Running ff ({ff_fstf}) ...")
    ff_t, ff_status = run_ff(ff_fstf)
    print(f"  ff        : {ff_t:.2f}s [{ff_status}]")

    print(f"  Running ffconnect ({ffc_fstf}) ...")
    ffc_t, ffc_status = run_ffconnect(TEST_DIR / ffc_fstf)
    print(f"  ffconnect : {ffc_t:.2f}s [{ffc_status}]")

    overhead = ffc_t - ff_t
    ratio    = ffc_t / ff_t if ff_t > 0 else float("nan")
    rows.append({
        "turbines":         turbines,
        "ff_time_s":        round(ff_t,  3),
        "ffconnect_time_s": round(ffc_t, 3),
        "overhead_s":       round(overhead, 3),
        "ratio":            round(ratio, 4),
        "ff_status":        ff_status,
        "ffconnect_status": ffc_status,
    })

with open(OUT_CSV, "w", newline="") as f:
    writer = csv.DictWriter(
        f, fieldnames=["turbines", "ff_time_s", "ffconnect_time_s", "overhead_s", "ratio", "ff_status", "ffconnect_status"]
    )
    writer.writeheader()
    writer.writerows(rows)

print(f"\nResults saved to {OUT_CSV}")
print(f"\n{'Turbines':>8}  {'ff (s)':>10}  {'ffconnect (s)':>14}  {'overhead (s)':>13}  {'ratio':>7}")
print("-" * 62)
for r in rows:
    print(
        f"{r['turbines']:>8}  {r['ff_time_s']:>10.2f}  "
        f"{r['ffconnect_time_s']:>14.2f}  "
        f"{r['overhead_s']:>13.2f}  "
        f"{r['ratio']:>7.4f}"
    )
