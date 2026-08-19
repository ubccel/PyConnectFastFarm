"""
Timing experiment: measure ffconnect wall-clock runtime on
demo/time/Test/ffconnect.fstf across OMP_NUM_THREADS = 2..24 (step 2),
to find the core count that gives the fastest run.

Each case runs in its own `mpiexec -n 1 python` subprocess so
OMP_NUM_THREADS can be set per-run via the subprocess environment
(the in-process MPI spawn used by ffconnect doesn't reliably pick up
env changes made after MPI_Init).

Results are saved to results/omp_threads_timing.csv.

Run with: python run_omp_threads_experiment.py
"""

import csv
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKER = ROOT / "_omp_worker_ffconnect.py"
OUT_CSV = ROOT / "results" / "omp_threads_timing.csv"

THREAD_COUNTS = list(range(2, 25, 2))


def run_case(n_threads: int):
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = str(n_threads)

    result_file = OUT_CSV.parent / f"_omp_elapsed_{n_threads}.txt"
    if result_file.exists():
        result_file.unlink()
    env["OMP_RESULT_FILE"] = str(result_file)

    # stdout/stderr inherit the console so FAST.Farm progress is visible live.
    proc = subprocess.run(
        ["mpiexec", "-n", "1", "python", str(WORKER)],
        cwd=str(ROOT), env=env,
    )

    if proc.returncode == 0 and result_file.exists():
        elapsed = float(result_file.read_text().strip())
        result_file.unlink()
        return elapsed, "OK"
    return float("nan"), f"ERROR (rc={proc.returncode})"


# ============================================================
# Experiment
# ============================================================

OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

rows = []
for n in THREAD_COUNTS:
    print(f"\n=== OMP_NUM_THREADS = {n}  ({THREAD_COUNTS.index(n) + 1}/{len(THREAD_COUNTS)}) ===", flush=True)
    print("  running ffconnect.fstf (this takes a few minutes) ...", flush=True)
    elapsed, status = run_case(n)
    print(f"  elapsed: {elapsed:.2f}s [{status}]", flush=True)
    rows.append({"omp_num_threads": n, "elapsed_s": round(elapsed, 3), "status": status})

with open(OUT_CSV, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["omp_num_threads", "elapsed_s", "status"])
    writer.writeheader()
    writer.writerows(rows)

print(f"\nResults saved to {OUT_CSV}")
print(f"\n{'OMP_NUM_THREADS':>15}  {'elapsed (s)':>12}  status")
print("-" * 60)
for r in rows:
    print(f"{r['omp_num_threads']:>15}  {r['elapsed_s']:>12.2f}  {r['status']}")

ok_rows = [r for r in rows if r["status"] == "OK"]
if ok_rows:
    best = min(ok_rows, key=lambda r: r["elapsed_s"])
    print(f"\nFastest: OMP_NUM_THREADS={best['omp_num_threads']} ({best['elapsed_s']:.2f}s)")
