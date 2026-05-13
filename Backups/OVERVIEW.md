# Backups Overview

This directory contains backup snapshots of simulation case files and supercontroller DLL source code.
The live copies of simulation directories live at `D:\2_PhD_UBC\Code\FASTv355\` (outside this repo).
The live DLL source code lives at `D:\2_PhD_UBC\Code\FASTv355\5MW_Baseline\ServoData\`.

---

## Cases (`backups/cases/`)

Each subdirectory is a complete snapshot of a FAST.Farm simulation directory. All cases use the
per-turbine DLL isolation pattern (one separate DISCON copy per turbine) required on Windows.

### Comparison Table

| Case | Platform | Turbines | SC_DLL | NumCtrl2SC | DISCON variant | DT_Low | Run script |
|------|----------|----------|--------|-----------|----------------|--------|------------|
| `SteadyWind_ffconnect_full` | Onshore (fixed) | 2 | `SC_DLL_Full.dll` | 69 | `DISCON_MPI_IPC_Full` | 0.1 s | `run_test_fullIO.py` |
| `SteadyWind_FOWF_ffconnect_full` | Floating (OC4 semi-sub) | 3 | `SC_DLL_Full.dll` | 69 | `DISCON_OC3Hywind_MPI_IPC_Full` | 0.1 s | `run_test_fullIO.py` |
| `SteadyWind_FOWF_ffconnect_turbRepo` | Floating (OC4 semi-sub) | 2 | `SC_DLL_Full.dll` | 69 | `DISCON_OC3Hywind_MPI_IPC_Full` | 3.0 s | `run_test_fullIO.py` |

All cases use `per_turbine_flags=True` in Python.

### Detailed Case Notes

#### `SteadyWind_ffconnect_full`

- **Purpose**: Fixed-bottom onshore farm with maximum IO (all 69 signals) for comprehensive structural state observation and controller parameter readback.
- **Turbine model**: NREL 5-MW onshore, fixed-bottom support structure.
- **SC_DLL**: `SC_DLL_Full.dll` — 69 measurements per turbine (shaft loads, hub/yaw-bearing moments, nacelle IMU accelerations, platform 6-DOF velocities & accelerations, controller parameter readbacks, and all basic signals).
- **DISCON**: `DISCON_MPI_IPC_Full_WT{1,2}.dll` — onshore baseline extended with 69-signal `to_SC` output.
- **Per-turbine chain**: `FFTest_WT{1,2}.fst` → `NRELOffshrBsline5MW_Onshore_ServoDyn_T{1,2}.dat` → `DISCON_MPI_IPC_Full_WT{1,2}.dll`

#### `SteadyWind_FOWF_ffconnect_full`

- **Purpose**: Floating offshore wind farm with maximum IO (69 signals) for comprehensive monitoring including platform dynamics.
- **Turbine model**: NREL 5-MW on OC4 DeepCwind semi-submersible platform; includes HydroDyn, MoorDyn, and MAP mooring.
- **SC_DLL**: `SC_DLL_Full.dll` — 69 measurements per turbine; platform velocity and acceleration signals are physically meaningful for floating platforms.
- **DISCON**: `DISCON_OC3Hywind_MPI_IPC_Full_WT{1,2,3}.dll` — OC3 Hywind baseline extended with 69-signal `to_SC` output.
- **Per-turbine chain**: `5MW_OC4Semi_WSt_WavesWN_T{1,2,3}.fst` → `NRELOffshrBsline5MW_OC4DeepCwindSemi_ServoDyn_T{1,2,3}.dat` → `DISCON_OC3Hywind_MPI_IPC_Full_WT{1,2,3}.dll`

#### `SteadyWind_FOWF_ffconnect_turbRepo`

- **Purpose**: Floating turbine repositioning for wake avoidance. Slack mooring lines allow each OC4 semi-sub platform to drift 100+ m horizontally, enabling the downstream turbine to move laterally out of the upstream wake.
- **Turbine model**: NREL 5-MW on OC4 DeepCwind semi-submersible; 2 turbines at ~5D spacing (625 m).
- **SC_DLL**: `SC_DLL_Full.dll` — 69 measurements per turbine. Primary repositioning feedback is `platform_tdx/tdy` (surge/sway displacements).
- **DISCON**: `DISCON_OC3Hywind_MPI_IPC_Full_WT{1,2}.dll` — same as `FOWF_full` variant.
- **Per-turbine chain**: `5MW_OC4Semi_WSt_WavesWN_T{1,2}.fst` → `NRELOffshrBsline5MW_OC4DeepCwindSemi_ServoDyn_T{1,2}.dat` → `DISCON_OC3Hywind_MPI_IPC_Full_WT{1,2}.dll`
- **Key difference — mooring**: `NRELOffshrBsline5MW_OC4DeepCwindSemi_MoorDyn_turbRepo.dat` sets line unstretched length to **970 m** (vs 835.35 m in the standard OC4 design). All anchor/fairlead positions are unchanged.
- **Key difference — timestep**: `DT_Low = 3.0 s` (vs 0.1 s in other cases). Adequate for slow platform-repositioning control; too coarse for blade-load feedback (<0.5 samples/revolution at ~8 rpm).
- **Known simulation behaviour**:
  - MoorDyn catenary solver fails at startup (excess line slack causes seabed contact outside the solver's hanging-chain assumption); dynamic relaxation converges in ~34 s — not fatal.
  - `SmllRotTrans` warning appears around t ≈ 100 s due to large blade deflection from platform tilt; simulation continues.
  - `platform_rdx/rdy/rdz` are in **degrees** (matching ElastoDyn output convention), despite the `# rad` comment in older code versions.

---

## Supercontrollers (`backups/supercontrollers/`)

Source code snapshots and pre-built DLL files. All are compiled with CMake + Intel Fortran (`ifx`) +
MS-MPI. See `CLAUDE.md` for rebuild commands.

### SC_DLL Variants

SC_DLL is the farm-level MPI communication bridge — it has no control logic of its own.
It receives Python commands via MPI and forwards them to each turbine's DISCON via the `from_SC` array,
and collects measurements from DISCON via the `to_SC` array.

| DLL | Source dir | NumCtrl2SC | NumSC2Ctrl | Flag mode |
|-----|-----------|-----------|-----------|-----------|
| `SC_DLL.dll` | `Baseline/SC_DLL/` | 12 | 6 | Global |
| `SC_DLL_More.dll` | `More/SC_DLL_More/` | 27 | 10 | Per-turbine |
| `SC_DLL_Full.dll` | `Full/SC_DLL_Full/` | 69 | 10 | Per-turbine |

**Global flag layout** (`SC_DLL.dll`, `per_turbine_flags=False`):
```
YAW/PITCH/TORQUE array:  [global_flag, T0_val, T1_val, ...]       size = N+1
IPC array:               [global_flag, T0_b1, T0_b2, T0_b3, ...]  size = 3N+1
```
Setting any turbine's value activates the flag for all turbines. Turbines with a 0 setpoint have
their DISCON overridden with 0 — torque collapses to zero, pitch locks at 0.

**Per-turbine flag layout** (`SC_DLL_More.dll`, `SC_DLL_Full.dll`, `per_turbine_flags=True`):
```
YAW/PITCH/TORQUE array:  [T0_flag, T0_val, T1_flag, T1_val, ...]              size = 2N
IPC array:               [T0_flag, T0_b1, T0_b2, T0_b3, T1_flag, T1_b1, ...]  size = 4N
```
Each turbine's flag is independent. Always use this mode for multi-turbine experiments.

### DISCON Variants

DISCON implements the turbine-level NREL 5-MW baseline controller extended with an MPI `from_SC`/`to_SC`
interface. The Baseline variants are stock controllers with no MPI capability.

| DLL | Source dir | Platform | IPC | NumCtrl2SC |
|-----|-----------|----------|-----|-----------|
| `DISCON.dll` | `Baseline/DISCON/` | Onshore | No | 12 |
| `DISCON_OC3Hywind.dll` | `Baseline/DISCON_OC3/` | FOWF | No | 12 |
| `DISCON_MPI_IPC_More.dll` | `More/DISCON_MPI_IPC_More/` | Onshore | Yes | 27 |
| `DISCON_OC3Hywind_MPI_IPC_More.dll` | `More/DISCON_OC3_MPI_IPC_More/` | FOWF | Yes | 27 |
| `DISCON_MPI_IPC_Full.dll` | `Full/DISCON_MPI_IPC_Full/` | Onshore | Yes | 69 |
| `DISCON_OC3Hywind_MPI_IPC_Full.dll` | `Full/DISCON_OC3_MPI_IPC_Full/` | FOWF | Yes | 69 |

#### `from_SC` interface (all MPI variants)

```
from_SC(1) = yaw activation flag    (1.0 = external yaw override active)
from_SC(2) = pitch activation flag  (1.0 = external CPC override active)
from_SC(3) = torque activation flag (1.0 = external torque override active)
from_SC(4) = yaw reference          (rad)
from_SC(5) = pitch reference        (rad)
from_SC(6) = torque reference       (N-m)
--- More/Full only (NumSC2Ctrl=10) ---
from_SC(7)  = IPC activation flag   (1.0 = IPC offsets active)
from_SC(8)  = IPC blade 1 offset    (rad)
from_SC(9)  = IPC blade 2 offset    (rad)
from_SC(10) = IPC blade 3 offset    (rad)
```

IPC offsets are superimposed on CPC output (`avrSWAP(42+k) = PitCom(k) + IPCRef(k)`) without
modifying the SAVE'd `PitCom` variable, preventing accumulation into the CPC rate limiter.

---

## Choosing the Right Combination

| Goal | SC_DLL | DISCON | `per_turbine_flags` |
|------|--------|--------|---------------------|
| Maximum IO — all 69 signals (onshore) | `SC_DLL_Full.dll` | `DISCON_MPI_IPC_Full` | `True` |
| Maximum IO — all 69 signals (floating) | `SC_DLL_Full.dll` | `DISCON_OC3Hywind_MPI_IPC_Full` | `True` |
