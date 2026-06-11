# Run with:  mpiexec -n 1 python run_time_experiment.py
"""
Timing experiment: compare wall-clock runtime of direct FAST.Farm (ff) vs
the Python ffconnect interface (ffconnect) for TMax = 500..3000 s in 500 s steps.
No control is applied in either case.
Results are saved to results/time_experiment.csv.
"""

import csv
import os
import subprocess
import time
from pathlib import Path

from openfast_toolbox.io.fast_input_file import FASTInputFile

from ffconnect.interface import FastFarmInterface

# ============================================================
# Paths
# ============================================================
FF_EXE     = r"D:\2_PhD_UBC\Code\FASTv355\FAST.Farm_x64_v355.exe"
FF_EXE_OMP = r"D:\2_PhD_UBC\Code\FASTv355\FAST.Farm_x64_OMP_v355.exe"
DEMO_DIR   = Path(r"D:\2_PhD_UBC\Code\PyConnectFastFarm\demo\time\LongerTime")
FF_FSTF    = DEMO_DIR / "ff.fstf"
FFC_FSTF   = DEMO_DIR / "ffconnect.fstf"
OUT_CSV    = Path(r"D:\2_PhD_UBC\Code\PyConnectFastFarm\results\time_experiment.csv")

TMAX_VALUES = [500, 1000, 1500, 2000, 2500, 3000]


# ============================================================
# Helpers
# ============================================================

def make_temp_fstf(src: Path, tmax: float, stem: str) -> Path:
    """Write a copy of src with TMax=tmax to DEMO_DIR/<stem>.fstf."""
    dst = DEMO_DIR / f"{stem}.fstf"
    fstf = FASTInputFile(str(src))
    fstf["TMax"] = float(tmax)
    fstf.write(str(dst))
    return dst


def cleanup_temp(path: Path) -> None:
    """Delete the temp .fstf and any FAST.Farm output files sharing its stem."""
    stem = path.stem
    for f in DEMO_DIR.glob(f"{stem}*"):
        try:
            f.unlink()
        except OSError:
            pass


def _is_released(path: Path) -> bool:
    if not path.exists():
        return True
    try:
        os.replace(path, path)
        return True
    except OSError:
        return False


def wait_for_file_release(paths, timeout: float = 120.0, poll_interval: float = 0.5) -> None:
    """Block until none of `paths` are still held open by another process.

    Used after the ffconnect simulation loop ends, since the spawned
    FAST.Farm process may still be flushing/closing output files after
    MPI_COMM_DISCONNECT returns. Falls through after `timeout` with a
    warning if files remain locked (cleanup_temp will then just skip them,
    same as today).
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if all(_is_released(p) for p in paths):
            return
        time.sleep(poll_interval)
    print(f"  Warning: some output files still locked after {timeout:.0f}s")


def run_ff(tmax: int) -> float:
    """Run direct FAST.Farm for the given TMax; return wall-clock seconds."""
    tmp = make_temp_fstf(FF_FSTF, tmax, f"_tmp_ff_{tmax}")
    t0 = time.perf_counter()
    subprocess.run([FF_EXE_OMP, str(tmp)], check=True, cwd=str(DEMO_DIR))
    elapsed = time.perf_counter() - t0
    cleanup_temp(tmp)
    return elapsed


def run_ffconnect(tmax: int) -> float:
    """Run ffconnect interface (no control) for the given TMax; return wall-clock seconds."""
    tmp = make_temp_fstf(FFC_FSTF, tmax, f"_tmp_ffc_{tmax}")
    interface = FastFarmInterface.from_file(
        str(tmp), fast_farm_executable=FF_EXE_OMP, per_turbine_flags=True
    )
    t0 = time.perf_counter()
    interface.init()
    done = False
    while not done:
        done = interface.step()
        # All channels passed as None — no control override
        for i in range(interface.num_turbines):
            interface.set_command(yaw=None, ipc=None, torque=None, turb_idx=i)
    # interface.step() returning True means MPI_COMM_DISCONNECT/FINALIZE
    # already happened on the FAST.Farm side, but the spawned process may
    # still be writing/closing its output files. Wait for that to finish
    # so the timer captures the same "full run" as run_ff's subprocess.run.
    wait_for_file_release(list(DEMO_DIR.glob(f"{tmp.stem}*")))
    elapsed = time.perf_counter() - t0
    cleanup_temp(tmp)
    return elapsed


# ============================================================
# Experiment
# ============================================================

OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

rows = []
for tmax in TMAX_VALUES:
    print(f"\n=== TMax = {tmax}s ===")

    print("  Running ff ...")
    ff_t = run_ff(tmax)
    print(f"  ff        : {ff_t:.2f}s")

    print("  Running ffconnect ...")
    ffc_t = run_ffconnect(tmax)
    print(f"  ffconnect : {ffc_t:.2f}s")

    overhead = ffc_t - ff_t
    ratio    = ffc_t / ff_t if ff_t > 0 else float("nan")
    rows.append({
        "tmax":             tmax,
        "ff_time_s":        round(ff_t,   3),
        "ffconnect_time_s": round(ffc_t,  3),
        "overhead_s":       round(overhead, 3),
        "ratio":            round(ratio,  4),
    })

with open(OUT_CSV, "w", newline="") as f:
    writer = csv.DictWriter(
        f, fieldnames=["tmax", "ff_time_s", "ffconnect_time_s", "overhead_s", "ratio"]
    )
    writer.writeheader()
    writer.writerows(rows)

print(f"\nResults saved to {OUT_CSV}")
print(f"\n{'TMax':>6}  {'ff (s)':>10}  {'ffconnect (s)':>14}  {'overhead (s)':>13}  {'ratio':>7}")
print("-" * 60)
for r in rows:
    print(
        f"{r['tmax']:>6}  {r['ff_time_s']:>10.2f}  "
        f"{r['ffconnect_time_s']:>14.2f}  "
        f"{r['overhead_s']:>13.2f}  "
        f"{r['ratio']:>7.4f}"
    )
