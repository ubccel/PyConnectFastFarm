# Run with: mpiexec -n 1 python _omp_worker_ffconnect.py
# Writes the measured wall-clock seconds to the file given by the
# OMP_RESULT_FILE env var (set by run_omp_threads_experiment.py); if that
# var is unset it just prints the time. Worker stdout/stderr stream live to
# the console so the orchestrator can show real-time FAST.Farm progress.
import os
import time
from pathlib import Path

from ffconnect.interface import FastFarmInterface

EXE = r"D:\2_PhD_UBC\Code\FASTv355\FAST.Farm_x64_OMP_v355.exe"
FSTF = Path(__file__).resolve().parent / "demo" / "time" / "CoreNum" / "ffconnect.fstf"

t0 = time.perf_counter()
interface = FastFarmInterface.from_file(str(FSTF), fast_farm_executable=EXE, per_turbine_flags=True)
interface.init()
done = False
while not done:
    done = interface.step()
elapsed = time.perf_counter() - t0

print(f"ELAPSED_S={elapsed:.6f}", flush=True)

result_file = os.environ.get("OMP_RESULT_FILE")
if result_file:
    Path(result_file).write_text(f"{elapsed:.6f}")
