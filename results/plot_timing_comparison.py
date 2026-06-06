"""Plot ffconnect vs pure FAST.Farm runtime comparisons from the timing experiments."""
import csv
import os

import matplotlib.pyplot as plt

plt.rcParams.update({"font.size": 14})

RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))


def load_csv(filename):
    path = os.path.join(RESULTS_DIR, filename)
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


# --- Figure 1: runtime vs. simulation length (same farm config) ---
sim_rows = load_csv("time_experiment.csv")
sim_rows.sort(key=lambda r: float(r["tmax"]))
tmax = [float(r["tmax"]) for r in sim_rows]
ff_sim_time = [float(r["ff_time_s"]) for r in sim_rows]
ffconnect_sim_time = [float(r["ffconnect_time_s"]) for r in sim_rows]

fig1, ax1 = plt.subplots(figsize=(12, 6))
# fig1.suptitle("Runtime vs. Simulation Length", fontsize=13)
ax1.plot(tmax, ff_sim_time, marker="o", label="FAST.Farm")
ax1.plot(tmax, ffconnect_sim_time, marker="o", linestyle="--", label="FFConnect")
ax1.set_xlabel("Simulation length, Tmax (s)")
ax1.set_ylabel("Runtime (s)")
ax1.legend()
ax1.grid(True)
fig1.tight_layout()
fig1.savefig(os.path.join(RESULTS_DIR, "runtime_vs_simtime.png"))

# --- Figure 2: runtime vs. farm size (same simulation length) ---
ff_rows = load_csv("ff_timing_results.csv")
ffconnect_rows = load_csv("ffconnect_timing_results.csv")
ff_rows.sort(key=lambda r: int(r["turbines"]))
ffconnect_rows.sort(key=lambda r: int(r["turbines"]))

ff_turbines = [int(r["turbines"]) for r in ff_rows]
ff_farm_time = [float(r["elapsed_seconds"]) for r in ff_rows]
ffconnect_turbines = [int(r["turbines"]) for r in ffconnect_rows]
ffconnect_farm_time = [float(r["elapsed_seconds"]) for r in ffconnect_rows]

fig2, ax2 = plt.subplots(figsize=(12, 6))
# fig2.suptitle("Runtime vs. Farm Size", fontsize=13)
ax2.plot(ff_turbines, ff_farm_time, marker="o", label="FAST.Farm")
ax2.plot(ffconnect_turbines, ffconnect_farm_time, marker="o", linestyle="--", label="FFConnect")
ax2.set_xlabel("Number of turbines")
ax2.set_ylabel("Runtime (s)")
ax2.legend()
ax2.grid(True)
fig2.tight_layout()
fig2.savefig(os.path.join(RESULTS_DIR, "runtime_vs_farmsize.png"))

plt.show()
