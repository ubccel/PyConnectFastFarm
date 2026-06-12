# PyConnectFastFarm

A lightweight Python interface for running **FAST.Farm v3.5.5** wind farm simulations step-by-step from a Python script. It handles MPI process management and measurement I/O so you can focus on writing control logic.

**This package does NOT generate FAST.Farm case files.** It requires an existing, fully configured FAST.Farm simulation directory (`.fstf` file + input files + compiled DLLs). Ready-to-use example cases are provided in `backups/cases/`.

Designed for reinforcement learning policy training and closed-loop wind farm control research. Only compatible with **FAST.Farm v3.5.5** (see [Version Compatibility](#8-fastfarm-version-compatibility)).

---

## Table of Contents

1. [Installation](#1-installation)
2. [Quick Start](#2-quick-start)
3. [API Reference](#3-api-reference)
4. [Measurements (69 signals)](#4-measurements-69-signals)
5. [Example Cases](#5-example-cases)
6. [MPI Communication](#6-mpi-communication)
7. [Troubleshooting](#7-troubleshooting)
8. [FAST.Farm Version Compatibility](#8-fastfarm-version-compatibility)

---

## 1. Installation

```bash
pip install -e .                      # install package (editable)
conda install intel-fortran-rt        # required Fortran runtime for SC_DLL and DISCON DLLs
```

**MS-MPI** (Windows): Install both the runtime and SDK from the Microsoft download page. All simulation scripts must be launched via MPI — bare `python` will hang:

```bash
mpiexec -n 1 python yourscript.py
```

---

## 2. Quick Start

Point `from_file()` at an existing `.fstf` file. The interface reads timestep, number of turbines, and simulation length automatically.

```python
from ffconnect.interface import FastFarmInterface

FFexePath = "path/to/FAST.Farm_x64_OMP_v355.exe"
FFsimPath = "path/to/FAST.Farm.fstf"

interface = FastFarmInterface.from_file(
    FFsimPath,
    fast_farm_executable=FFexePath,
    per_turbine_flags=True,
)
interface.init(wind_speed=9.0)

n_turbines = interface.num_turbines
max_iter   = interface.max_iter

for step in range(max_iter):
    done = interface.step()
    power = interface.get_measure("power", turb_idx=0).item()   # W
    if done:
        break
    for i in range(n_turbines):
        interface.set_command(
            yaw    = 10.0,  # deg — or pass None to leave to DISCON
            pitch  = None,
            torque = None,
            ipc    = None,
            turb_idx = i,
        )
```

**Loop order — step first**: always call `step()` before `get_measure()`. `current_measures` is only populated inside `step()`, so reading before stepping returns the uninitialized t=0 buffer (NaN/garbage). Set commands after reading — they are buffered and consumed by the *next* `step()` call.

**Key rule — `None` guards**: always pass `None` for channels you are not controlling. Passing `0.0` activates the override flag with a zero setpoint and overrides DISCON (torque or pitch collapses to zero).

---

## 3. API Reference

### `FastFarmInterface.from_file()`

```python
interface = FastFarmInterface.from_file(
    fstf_file,                                  # path to FAST.Farm.fstf
    fast_farm_executable = default_exe_path,    # optional override
    per_turbine_flags    = False,               # set True for SC_DLL_Full
)
```

Reads `DT_Low`, `TMax`, and `NumTurbines` from the `.fstf` file. DLLs must already be in the simulation directory. Use `per_turbine_flags=True` when using `SC_DLL_Full.dll`.

**Instance attributes**

| Attribute | Description |
|-----------|-------------|
| `num_turbines` | Number of turbines in the farm |
| `max_iter` | Total simulation steps (`TMax / DT_Low`) |
| `dt` | Timestep in seconds (`DT_Low`) |

**Methods**

| Method | Description |
|--------|-------------|
| `init(wind_speed, wind_direction)` | Spawn FAST.Farm via MPI and complete the SC_DLL handshake. Call once before the loop. `wind_speed` overwrites `HWindSpeed` in the InflowWind file if provided. |
| `set_command(yaw, pitch, torque, ipc, turb_idx)` | Buffer a command for one turbine (0-based index). Pass `None` for any channel left to the DISCON baseline controller. `ipc` is a 3-element array of per-blade pitch offsets (rad). |
| `step()` | Send all buffered commands via MPI and advance one timestep. Returns `True` when the simulation is complete. |
| `get_measure(name, turb_idx=None)` | Retrieve the latest measurement by name. With `turb_idx`, returns a single-turbine scalar array; without it, returns the full `(n_turbines,)` array. Use `.item()` to extract Python scalars. |
| `avg_powers(window, turb_idx=None)` | Rolling-average power (W) over the last `window` timesteps. |

Default executable: `ffconnect/simulator/fastfarm/bin/FAST.Farm_x64_OMP_v355.exe`

---

## 4. Measurements (69 signals)

This package supports only the **Full variant** (`SC_DLL_Full.dll`, `NumCtrl2SC = 69`). The measure map is validated automatically after the MPI handshake — if the SC_DLL reports a different `NumCtrl2SC` value, the wrong DLL is loaded.

### Indices 0–26 (base signals)

| Name | Unit | Index | Description |
|------|------|-------|-------------|
| `"rotor_speed"` | rad/s | 0 | Rotor angular speed |
| `"generator_speed"` | rad/s | 1 | Generator angular speed |
| `"power"` | W | 2 | Electrical output power |
| `"wind_speed"` | m/s | 3 | Hub-height wind speed |
| `"yaw"` | **rad** | 4 | Nacelle yaw angle |
| `"pitch"` | **rad** | 5 | Blade 1 pitch angle |
| `"pitch_blade2"` | **rad** | 6 | Blade 2 pitch angle |
| `"pitch_blade3"` | **rad** | 7 | Blade 3 pitch angle |
| `"load"` | N-m | 8–13 | Blade root loads, shape `(N, 6)`: OOP moments (blades 1–3), IP moments (blades 1–3) |
| `"tower_fa_accel"` | m/s² | 14 | Tower top fore-aft acceleration |
| `"tower_ss_accel"` | m/s² | 15 | Tower top side-side acceleration |
| `"time"` | s | 16 | Current simulation time |
| `"azimuth"` | **rad** | 17 | Low-speed shaft azimuth angle |
| `"torque"` | N-m | 18 | Generator torque |
| `"wind_speed_hub"` | m/s | 19 | Hub wind speed (duplicate of `wind_speed`) |
| `"wind_direction"` | deg | 20 | Local wind direction (auto-converted from rad by interface) |
| `"platform_tdx"` | m | 21 | Platform surge (X) displacement |
| `"platform_tdy"` | m | 22 | Platform sway (Y) displacement |
| `"platform_tdz"` | m | 23 | Platform heave (Z) displacement |
| `"platform_rdx"` | **rad** | 24 | Platform roll |
| `"platform_rdy"` | **rad** | 25 | Platform pitch |
| `"platform_rdz"` | **rad** | 26 | Platform yaw |

### Indices 27–68 (additional signals)

| Name | Unit | Index | Description |
|------|------|-------|-------------|
| `"shaft_power"` | W | 27 | Shaft power |
| `"hub_my_rotating"` | N-m | 28 | Hub moment My (rotating frame) |
| `"hub_mz_rotating"` | N-m | 29 | Hub moment Mz (rotating frame) |
| `"hub_my_fixed"` | N-m | 30 | Hub moment My (fixed frame) |
| `"hub_mz_fixed"` | N-m | 31 | Hub moment Mz (fixed frame) |
| `"yaw_bearing_my"` | N-m | 32 | Yaw bearing moment My |
| `"yaw_bearing_mz"` | N-m | 33 | Yaw bearing moment Mz |
| `"nacelle_roll_accel"` | rad/s² | 34 | Nacelle roll angular acceleration |
| `"nacelle_nodding_accel"` | rad/s² | 35 | Nacelle nodding angular acceleration |
| `"nacelle_yaw_accel"` | rad/s² | 36 | Nacelle yaw angular acceleration |
| `"air_density"` | kg/m³ | 37 | Ambient air density |
| `"rotor_avg_wind_speed"` | m/s | 38 | Rotor-disk-averaged wind speed |
| `"shaft_torque"` | N-m | 39 | Low-speed shaft torque |
| `"shaft_thrust"` | N | 40 | Rotor thrust (shaft axial force) |
| `"shaft_force_y"` | N | 41 | Shaft shear force Y (fixed frame) |
| `"shaft_force_z"` | N | 42 | Shaft shear force Z (fixed frame) |
| `"platform_tvx"` | m/s | 43 | Platform surge velocity |
| `"platform_tvy"` | m/s | 44 | Platform sway velocity |
| `"platform_tvz"` | m/s | 45 | Platform heave velocity |
| `"platform_rvx"` | rad/s | 46 | Platform roll rate |
| `"platform_rvy"` | rad/s | 47 | Platform pitch rate |
| `"platform_rvz"` | rad/s | 48 | Platform yaw rate |
| `"platform_tax"` | m/s² | 49 | Platform surge acceleration |
| `"platform_tay"` | m/s² | 50 | Platform sway acceleration |
| `"platform_taz"` | m/s² | 51 | Platform heave acceleration |
| `"platform_rax"` | rad/s² | 52 | Platform roll acceleration |
| `"platform_ray"` | rad/s² | 53 | Platform pitch acceleration |
| `"platform_raz"` | rad/s² | 54 | Platform yaw acceleration |
| `"dll_dt"` | s | 55 | Controller timestep |
| `"pitch_min"` / `"pitch_max"` | rad | 56/57 | Blade pitch limits |
| `"pitch_rate_min"` / `"pitch_rate_max"` | rad/s | 58/59 | Pitch rate limits |
| `"demanded_power"` | W | 60 | Demanded electrical power |
| `"optimal_mode_gain"` | N-m/(rad/s)² | 61 | Optimal mode gain (torque law) |
| `"min_gen_speed_opt"` / `"max_gen_speed_opt"` | rad/s | 62/63 | Optimal mode generator speed bounds |
| `"demanded_gen_speed"` | rad/s | 64 | Demanded generator speed |
| `"demanded_gen_torque"` | N-m | 65 | Demanded generator torque |
| `"pitch_control_mode"` | flag | 66 | Pitch control mode flag |
| `"yaw_control_mode"` | flag | 67 | Yaw control mode flag |
| `"num_blades"` | count | 68 | Number of rotor blades |

**Unit notes**
- `yaw`, `pitch`, `pitch_blade2`, `pitch_blade3`, `azimuth` — **radians**. Use `np.degrees(val.item())` for display.
- `platform_rdx/rdy/rdz` — **radians**. These come through the DISCON super-controller path (`to_SC(25-27) = avrSWAP(1004-1006)`, radians), NOT ElastoDyn's degree-valued output file. Use `np.degrees(val.item())` for display, exactly as the run scripts do.
- `wind_direction` — **degrees**. Auto-converted by the interface.

---

## 5. Example Cases

Three ready-to-use simulation directories are in `backups/cases/`. Each contains the complete set of input files and pre-built DLLs.

| Case | Turbines | Platform | `DT_Low` | `NumPlanes` | DISCON |
|------|----------|----------|----------|-------------|--------|
| `SteadyWind_ffconnect_full` | 2 | Onshore (fixed) | 0.1 s | 439 | `DISCON_MPI_IPC_Full_WT{1,2}.dll` |
| `SteadyWind_FOWF_ffconnect_full` | 3 | OC4 semi-sub | 0.1 s | 1448 | `DISCON_OC3Hywind_MPI_IPC_Full_WT{1,2,3}.dll` |
| `SteadyWind_FOWF_ffconnect_turbRepo` | 2 | OC4 semi-sub (slack mooring) | 3.0 s | 87 | `DISCON_OC3Hywind_MPI_IPC_Full_WT{1,2}.dll` |

All cases use `SC_DLL_Full.dll` and `per_turbine_flags=True`.

The `turbRepo` case uses extended mooring lines (970 m vs 835 m standard) to allow large horizontal platform drift for wake-avoidance repositioning research. Its coarse `DT_Low = 3.0 s` is adequate for platform-level control but too sparse for blade-load feedback.

**Per-turbine DLL isolation (Windows — critical)**: each turbine must reference its own DISCON DLL copy. `LoadLibrary` returns the same handle for the same file path, causing Fortran `SAVE` variables to be shared across OpenMP threads and corrupting controller state (symptoms: torque drops to zero, pitch locks at 0°, rotor overspeeds).

```
FAST.Farm.fstf
  ├── T1.fst  →  ServoDyn_T1.dat  →  DISCON_Full_WT1.dll
  ├── T2.fst  →  ServoDyn_T2.dat  →  DISCON_Full_WT2.dll
  └── T3.fst  →  ServoDyn_T3.dat  →  DISCON_Full_WT3.dll
```

Fortran source for all DLLs is in `backups/supercontrollers/Full/`. Compiled with CMake + Intel Fortran (`ifx`) + MS-MPI.

---

## 6. MPI Communication

The simulation is strictly synchronous — Python and FAST.Farm advance in lock-step via MPI.

```
Python                              SC_DLL (inside FAST.Farm)
  │                                        │
  │── YAW_TAG    (tag=1) ─────────────►   │  yaw command array
  │── PITCH_TAG  (tag=2) ─────────────►   │  pitch command array
  │── TORQUE_TAG (tag=3) ─────────────►   │  torque command array
  │── IPC_TAG    (tag=5) ─────────────►   │  IPC command array
  │◄─ MEASURES_TAG (tag=4) ─────────────  │  [69 × N turbines]
  │── MPI_BARRIER ──────────────────────  │
  │                                        │
  │ (next timestep)                        │ (FAST.Farm advances physics)
```

**Handshake** (first timestep only): SC_DLL sends `NumCtrl2SC` → Python; Python sends `max_iter` → SC_DLL.

**Command array layout** (`per_turbine_flags=True`):
```
YAW / PITCH / TORQUE:  [T0_flag, T0_val, T1_flag, T1_val, ...]        size = 2N
IPC:                   [T0_flag, T0_b1, T0_b2, T0_b3, T1_flag, ...]   size = 4N
```
Each turbine's flag is independent — commanding T0 does not affect T1.

---

## 7. Troubleshooting

### Spawn hangs indefinitely
Run the executable standalone to diagnose:
```bash
FAST.Farm_x64_OMP_v355.exe Case.fstf
```
- Exit code `0xC0000135` → missing DLL. Run `conda install intel-fortran-rt`.
- Prints "This is not a spawned process" → binary is fine; ensure you launched with `mpiexec -n 1`.

### `from_file()` DLL checklist
1. **`UseSC = True`** in the `.fstf` file — without it FAST.Farm never loads the SC_DLL and Python hangs.
2. **SC-aware DISCON** — the stock NREL DISCON has no `from_SC`/`to_SC` interface; use the variants from `backups/supercontrollers/Full/`.
3. **Per-turbine DLL copies** — each turbine must reference a separate file path (see Section 5).

### `SmllRotTrans` warning
```
Small angle assumption violated in SUBROUTINE SmllRotTrans()
```
Common in floating cases with large platform motion. The simulation continues with the warning suppressed. Safe to ignore unless results diverge (NaN values, runaway rotor speed).

### `MPI_INIT` double-init crash
**Symptom**: FAST.Farm aborts with `Fatal error in MPI_Init: Cannot call MPI_INIT more than once`.

**Cause**: FAST.Farm calls `sc_calcOutputs` twice at t=0. The SC_DLL init guard must use `if (num_iter == 0)` (a `SAVE`'d counter), not `if (int(t) == 0)` — the latter fires twice and also misfires whenever `DT_Low < 1.0`.

---

## 8. FAST.Farm Version Compatibility

This package is **only compatible with FAST.Farm v3.5.5**. It does not work with v4.x.

FAST.Farm v4.1.0 removed the SuperController module entirely — the `UseSC` flag and `SC_FileName` parameter no longer exist. v4.x replaced the SC with distributed ROSCO controllers communicating via ZeroMQ (asynchronous), incompatible with step-locked RL training.

| Property | This package (v3.5.5 MPI) | ROSCO ZMQ (v4.x) |
|---|---|---|
| Synchronous step-lock | Yes | No |
| Python controls simulation pace | Yes | No |
| Suitable for RL training | Yes | Not supported |
