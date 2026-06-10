# Run with:     $env:OMP_NUM_THREADS = 24 (optional for acceleration)
#               mpiexec -n 1 python run_demo.py

import os
import pickle
import numpy as np
import matplotlib.pyplot as plt
from ffconnect.interface import FastFarmInterface


class RateLimiter:
    """Causal rate limiter: clamps how fast a commanded value may change per step."""

    def __init__(self, max_rate, dt):
        self.max_step = abs(max_rate) * dt
        self.value = None

    def reset(self, value=None):
        self.value = value

    def step(self, target):
        if self.value is None:
            self.value = target
        else:
            self.value += np.clip(target - self.value, -self.max_step, self.max_step)
        return self.value


# Yaw command rate limit (deg/s) — matches the saturation value SC_DLL_Full computes
# but never applies (from_SCglob(1) = 0.005235 rad/s ~= 0.3 deg/s).
YAW_RATE_LIMIT_DEG_S = 0.3

# ================================= Initialization =================================
save_results       = True
save_figure_option = True    # True → save PNGs to results/<run_name>/  |  False → interactive plt.show()
IO_check           = True
RESULTS_DIR        = "results"
result_file_name   = "demo_2x2_ctrl_checksign.pkl"
print_result = False
# --- User-defined paths ---
FFexePath = "D:\\2_PhD_UBC\\Code\\FASTv355\\FAST.Farm_x64_OMP_v355.exe"
# FFsimPath = "D:\\2_PhD_UBC\\Code\\FASTv355\\SteadyWind_FOWF_ffconnect_full\\FAST.Farm.fstf"  # floating (3T)
FFsimPath = "D:\\2_PhD_UBC\\Code\\PyConnectFastFarm\\demo\\examples\\2x2.fstf"  # fixed-bottom (2T)
# FFsimPath = "D:\\2_PhD_UBC\\Code\\FASTv355\\SteadyWind_FOWF_ffconnect_turbRepo\\FAST.Farm.fstf" # floating repositioning (2T)

# --- Initialize interface from .fstf file ---
interface = FastFarmInterface.from_file(FFsimPath, fast_farm_executable=FFexePath, per_turbine_flags=True)
interface.init()

n_turbines = interface.num_turbines
max_iter   = interface.max_iter
dt         = interface.dt

# ================================= Define Control =================================
yaw_schedule = np.zeros(max_iter)
ipc_schedule = np.zeros((max_iter, 3))
torque_schedule = np.zeros(max_iter)

activate_time = 60
activate_step = int(activate_time / dt)
yaw_schedule[activate_step:] = 10.0
ipc_schedule[activate_step:] = [1.0, 2.0, 3.0]
torque_schedule[activate_step:] = 35e3

yaw_limiters = [RateLimiter(YAW_RATE_LIMIT_DEG_S, dt) for _ in range(n_turbines)]

# --- Simulation loop ---
results = []
done = False

for t in range(max_iter):
    # Advance one step FIRST, then read the freshly computed measures.
    # current_measures is only populated inside step(), so stepping first
    # guarantees a valid (non-NaN) read — no spin-up NaN to filter around.
    done = interface.step()

    step_result = {"t": (t + 1) * dt}
    total_power = 0.0
    for i in range(n_turbines):
        # --- Variables shared with More variant ---
        power_i    = interface.get_measure("power",              turb_idx=i)
        pitch_b1   = interface.get_measure("pitch",              turb_idx=i)
        pitch_b2   = interface.get_measure("pitch_blade2",       turb_idx=i)
        pitch_b3   = interface.get_measure("pitch_blade3",       turb_idx=i)
        yaw_i      = interface.get_measure("yaw",                turb_idx=i)
        loads_i    = interface.get_measure("load",               turb_idx=i)
        torque_i   = interface.get_measure("torque",             turb_idx=i)
        wind_spd_i = interface.get_measure("wind_speed",         turb_idx=i)
        wind_dir_i = interface.get_measure("wind_direction",     turb_idx=i)
        tdx_i      = interface.get_measure("platform_tdx",       turb_idx=i)
        tdy_i      = interface.get_measure("platform_tdy",       turb_idx=i)
        tdz_i      = interface.get_measure("platform_tdz",       turb_idx=i)
        rdx_i      = interface.get_measure("platform_rdx",       turb_idx=i)
        rdy_i      = interface.get_measure("platform_rdy",       turb_idx=i)
        rdz_i      = interface.get_measure("platform_rdz",       turb_idx=i)
        rotor_spd_i  = interface.get_measure("rotor_speed",      turb_idx=i)
        gen_spd_i    = interface.get_measure("generator_speed",  turb_idx=i)
        fa_acc_i     = interface.get_measure("tower_fa_accel",   turb_idx=i)
        ss_acc_i     = interface.get_measure("tower_ss_accel",   turb_idx=i)
        azimuth_i    = interface.get_measure("azimuth",          turb_idx=i)
        # --- New Full-variant variables ---
        shaft_pwr_i  = interface.get_measure("shaft_power",          turb_idx=i)
        hub_myr_i    = interface.get_measure("hub_my_rotating",      turb_idx=i)
        hub_mzr_i    = interface.get_measure("hub_mz_rotating",      turb_idx=i)
        hub_myf_i    = interface.get_measure("hub_my_fixed",         turb_idx=i)
        hub_mzf_i    = interface.get_measure("hub_mz_fixed",         turb_idx=i)
        yb_my_i      = interface.get_measure("yaw_bearing_my",       turb_idx=i)
        yb_mz_i      = interface.get_measure("yaw_bearing_mz",       turb_idx=i)
        nc_roll_i    = interface.get_measure("nacelle_roll_accel",    turb_idx=i)
        nc_nod_i     = interface.get_measure("nacelle_nodding_accel", turb_idx=i)
        nc_yaw_i     = interface.get_measure("nacelle_yaw_accel",     turb_idx=i)
        air_den_i    = interface.get_measure("air_density",           turb_idx=i)
        rotor_avg_i  = interface.get_measure("rotor_avg_wind_speed",  turb_idx=i)
        sh_torq_i    = interface.get_measure("shaft_torque",          turb_idx=i)
        sh_thr_i     = interface.get_measure("shaft_thrust",          turb_idx=i)
        sh_fy_i      = interface.get_measure("shaft_force_y",         turb_idx=i)
        sh_fz_i      = interface.get_measure("shaft_force_z",         turb_idx=i)
        p_tvx_i      = interface.get_measure("platform_tvx",          turb_idx=i)
        p_tvy_i      = interface.get_measure("platform_tvy",          turb_idx=i)
        p_tvz_i      = interface.get_measure("platform_tvz",          turb_idx=i)
        p_rvx_i      = interface.get_measure("platform_rvx",          turb_idx=i)
        p_rvy_i      = interface.get_measure("platform_rvy",          turb_idx=i)
        p_rvz_i      = interface.get_measure("platform_rvz",          turb_idx=i)
        p_tax_i      = interface.get_measure("platform_tax",          turb_idx=i)
        p_tay_i      = interface.get_measure("platform_tay",          turb_idx=i)
        p_taz_i      = interface.get_measure("platform_taz",          turb_idx=i)
        p_rax_i      = interface.get_measure("platform_rax",          turb_idx=i)
        p_ray_i      = interface.get_measure("platform_ray",          turb_idx=i)
        p_raz_i      = interface.get_measure("platform_raz",          turb_idx=i)
        dll_dt_i     = interface.get_measure("dll_dt",                turb_idx=i)
        pt_min_i     = interface.get_measure("pitch_min",             turb_idx=i)
        pt_max_i     = interface.get_measure("pitch_max",             turb_idx=i)
        ptr_min_i    = interface.get_measure("pitch_rate_min",        turb_idx=i)
        ptr_max_i    = interface.get_measure("pitch_rate_max",        turb_idx=i)
        dem_pwr_i    = interface.get_measure("demanded_power",        turb_idx=i)
        omg_gain_i   = interface.get_measure("optimal_mode_gain",     turb_idx=i)
        gs_min_i     = interface.get_measure("min_gen_speed_opt",     turb_idx=i)
        gs_max_i     = interface.get_measure("max_gen_speed_opt",     turb_idx=i)
        dem_gs_i     = interface.get_measure("demanded_gen_speed",    turb_idx=i)
        dem_gt_i     = interface.get_measure("demanded_gen_torque",   turb_idx=i)
        pt_mode_i    = interface.get_measure("pitch_control_mode",    turb_idx=i)
        yaw_mode_i   = interface.get_measure("yaw_control_mode",      turb_idx=i)
        n_blades_i   = interface.get_measure("num_blades",            turb_idx=i)

        # --- Store (unit conversions done at plot time for readability) ---
        step_result[f"power_T{i}"]          = power_i.item()
        step_result[f"torque_T{i}"]         = torque_i.item()
        step_result[f"pitch_b1_T{i}"]       = np.degrees(pitch_b1.item())
        step_result[f"pitch_b2_T{i}"]       = np.degrees(pitch_b2.item())
        step_result[f"pitch_b3_T{i}"]       = np.degrees(pitch_b3.item())
        step_result[f"yaw_T{i}"]            = np.degrees(yaw_i.item())
        step_result[f"loads_T{i}"]          = loads_i.copy()
        step_result[f"wind_spd_T{i}"]       = wind_spd_i.item()
        step_result[f"wind_dir_T{i}"]       = wind_dir_i.item()
        step_result[f"platform_tdx_T{i}"]   = tdx_i.item()
        step_result[f"platform_tdy_T{i}"]   = tdy_i.item()
        step_result[f"platform_tdz_T{i}"]   = tdz_i.item()
        step_result[f"platform_rdx_T{i}"]   = np.degrees(rdx_i.item())
        step_result[f"platform_rdy_T{i}"]   = np.degrees(rdy_i.item())
        step_result[f"platform_rdz_T{i}"]   = np.degrees(rdz_i.item())
        step_result[f"rotor_spd_T{i}"]      = rotor_spd_i.item()
        step_result[f"gen_spd_T{i}"]        = gen_spd_i.item()
        step_result[f"tower_fa_T{i}"]       = fa_acc_i.item()
        step_result[f"tower_ss_T{i}"]       = ss_acc_i.item()
        step_result[f"azimuth_T{i}"]        = np.degrees(azimuth_i.item())
        step_result[f"shaft_pwr_T{i}"]      = shaft_pwr_i.item()
        step_result[f"hub_myr_T{i}"]        = hub_myr_i.item()
        step_result[f"hub_mzr_T{i}"]        = hub_mzr_i.item()
        step_result[f"hub_myf_T{i}"]        = hub_myf_i.item()
        step_result[f"hub_mzf_T{i}"]        = hub_mzf_i.item()
        step_result[f"yb_my_T{i}"]          = yb_my_i.item()
        step_result[f"yb_mz_T{i}"]          = yb_mz_i.item()
        step_result[f"nc_roll_T{i}"]        = nc_roll_i.item()
        step_result[f"nc_nod_T{i}"]         = nc_nod_i.item()
        step_result[f"nc_yaw_T{i}"]         = nc_yaw_i.item()
        step_result[f"air_den_T{i}"]        = air_den_i.item()
        step_result[f"rotor_avg_T{i}"]      = rotor_avg_i.item()
        step_result[f"sh_torq_T{i}"]        = sh_torq_i.item()
        step_result[f"sh_thr_T{i}"]         = sh_thr_i.item()
        step_result[f"sh_fy_T{i}"]          = sh_fy_i.item()
        step_result[f"sh_fz_T{i}"]          = sh_fz_i.item()
        step_result[f"p_tvx_T{i}"]          = p_tvx_i.item()
        step_result[f"p_tvy_T{i}"]          = p_tvy_i.item()
        step_result[f"p_tvz_T{i}"]          = p_tvz_i.item()
        step_result[f"p_rvx_T{i}"]          = p_rvx_i.item()
        step_result[f"p_rvy_T{i}"]          = p_rvy_i.item()
        step_result[f"p_rvz_T{i}"]          = p_rvz_i.item()
        step_result[f"p_tax_T{i}"]          = p_tax_i.item()
        step_result[f"p_tay_T{i}"]          = p_tay_i.item()
        step_result[f"p_taz_T{i}"]          = p_taz_i.item()
        step_result[f"p_rax_T{i}"]          = p_rax_i.item()
        step_result[f"p_ray_T{i}"]          = p_ray_i.item()
        step_result[f"p_raz_T{i}"]          = p_raz_i.item()
        step_result[f"dll_dt_T{i}"]         = dll_dt_i.item()
        step_result[f"pt_min_T{i}"]         = np.degrees(pt_min_i.item())
        step_result[f"pt_max_T{i}"]         = np.degrees(pt_max_i.item())
        step_result[f"ptr_min_T{i}"]        = np.degrees(ptr_min_i.item())
        step_result[f"ptr_max_T{i}"]        = np.degrees(ptr_max_i.item())
        step_result[f"dem_pwr_T{i}"]        = dem_pwr_i.item()
        step_result[f"omg_gain_T{i}"]       = omg_gain_i.item()
        step_result[f"gs_min_T{i}"]         = gs_min_i.item()
        step_result[f"gs_max_T{i}"]         = gs_max_i.item()
        step_result[f"dem_gs_T{i}"]         = dem_gs_i.item()
        step_result[f"dem_gt_T{i}"]         = dem_gt_i.item()
        step_result[f"pt_mode_T{i}"]        = pt_mode_i.item()
        step_result[f"yaw_mode_T{i}"]       = yaw_mode_i.item()
        step_result[f"n_blades_T{i}"]       = n_blades_i.item()
        total_power += power_i.item()

    results.append(step_result)
    if print_result:
        if t + 1 >= activate_step:
            print(
                f"t={(t+1)*dt:6.1f}s  power={total_power/1e6:.3f} MW  "
                f"pitch_T0=[{step_result['pitch_b1_T0']:.2f}, "
                f"{step_result['pitch_b2_T0']:.2f}, "
                f"{step_result['pitch_b3_T0']:.2f}] deg"
            )
        else:
            print(f"t={(t+1)*dt:6.1f}s  power={total_power/1e6:.3f} MW  (warmup)")

    if done:
        break

    # Per-turbine yaw P-controller: align nacelle to local wind direction.
    # Confirmed from DISCON Fortran source: yaw (to_SC[5]), wind_direction (to_SC[21]),
    # and platform_rdz (to_SC[27]) are all sent in radians. The interface pre-converts
    # wind_direction to degrees; yaw and platform_rdz need explicit np.degrees() calls.
    # Command is an absolute nacelle yaw angle in degrees (see set_command docstring).
    for turb in range(n_turbines):
        wind_dir_t = interface.get_measure("wind_direction", turb_idx=turb).item()             # deg
        yaw_t_deg  = np.degrees(interface.get_measure("yaw", turb_idx=turb).item())            # rad → deg
        rdz_t_deg  = np.degrees(interface.get_measure("platform_rdz", turb_idx=turb).item())   # rad → deg

        Kp = 1.0
        error_t       = (wind_dir_t - 270) - (yaw_t_deg)                                        # deg wind_dir_t - 270) - (yaw_t_deg - rdz_t_deg) 
        yaw_command_t = yaw_t_deg + Kp * error_t                                                # P(K=1) → wind_dir_t - rdz_t_deg

        if t + 1 == activate_step:
            yaw_limiters[turb].reset(yaw_t_deg)
        yaw_cmd_limited = yaw_limiters[turb].step(yaw_command_t)

        step_result[f"yaw_cmd_T{turb}"]    = yaw_cmd_limited
        step_result[f"yaw_target_T{turb}"] = yaw_command_t
        step_result[f"yaw_error_T{turb}"]  = error_t

        if t + 1 >= activate_step:
            interface.set_command(
                yaw=yaw_cmd_limited,
                ipc=None,
                torque=None,
                turb_idx=turb,
            )

# ================================= Output directory =================================
run_name = os.path.splitext(result_file_name)[0]
run_dir  = os.path.join(RESULTS_DIR, run_name)
os.makedirs(run_dir, exist_ok=True)

# ================================= Save Results =================================
if save_results:
    out_path = os.path.join(run_dir, result_file_name)
    with open(out_path, "wb") as f:
        pickle.dump(results, f)
    print(f"Results saved to {out_path} ({len(results)} steps)")

# ================================= Plotting =================================
t_arr = np.array([r["t"] for r in results])
blade_colors = ["tab:green", "tab:red", "tab:purple"]
blade_labels = ["Blade 1", "Blade 2", "Blade 3"]

def _savefig(fig, name):
    if save_figure_option:
        path = os.path.join(run_dir, f"{name}.png")
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"Saved: {path}")
        plt.close(fig)
    else:
        plt.show()

for i in range(n_turbines):
    if IO_check:
        # --- Figure A: T{i} I/O Verification (6 rows) ---
        fig, axes = plt.subplots(6, 1, figsize=(12, 20), sharex=True)
        fig.suptitle(f"FAST.Farm Full IO Test — T{i} Input/Output Verification", fontsize=13)

        power = np.array([r[f"power_T{i}"] for r in results]) / 1e6
        axes[0].plot(t_arr, power)
        axes[0].set_ylabel("Power (MW)")
        axes[0].grid(True)

        yaw_cmd  = yaw_schedule[:len(results)]
        yaw_meas = np.array([r[f"yaw_T{i}"] for r in results])
        axes[1].plot(t_arr, yaw_cmd,  linestyle="--", label="cmd")
        axes[1].plot(t_arr, yaw_meas, linestyle="-",  label="meas")
        axes[1].set_ylabel("Yaw (deg)")
        axes[1].legend()
        axes[1].grid(True)

        pitch_keys = [f"pitch_b1_T{i}", f"pitch_b2_T{i}", f"pitch_b3_T{i}"]
        for b, (bkey, bcol, blabel) in enumerate(zip(pitch_keys, blade_colors, blade_labels)):
            ipc_cmd    = ipc_schedule[:len(results), b]
            pitch_meas = np.array([r[bkey] for r in results])
            axes[2].plot(t_arr, ipc_cmd,    color=bcol, linestyle="--", label=f"{blabel} IPC cmd")
            axes[2].plot(t_arr, pitch_meas, color=bcol, linestyle="-",  label=f"{blabel} meas")
        axes[2].set_ylabel("Pitch (deg)")
        axes[2].legend(ncol=2)
        axes[2].grid(True)

        torque = np.array([r[f"torque_T{i}"] for r in results]) / 1e3
        axes[3].plot(t_arr, torque, color="tab:brown")
        axes[3].set_ylabel("Torque (kN·m)")
        axes[3].grid(True)

        ax_dir = axes[4].twinx()
        wspd = np.array([r[f"wind_spd_T{i}"] for r in results])
        wdir = np.array([r[f"wind_dir_T{i}"] for r in results])
        axes[4].plot(t_arr, wspd, color="steelblue",  label="Wind speed")
        ax_dir.plot( t_arr, wdir, color="darkorange", linestyle="--", label="Wind direction")
        axes[4].set_ylabel("Wind speed (m/s)", color="steelblue")
        ax_dir.set_ylabel("Wind direction (deg)", color="darkorange")
        lines1, labels1 = axes[4].get_legend_handles_labels()
        lines2, labels2 = ax_dir.get_legend_handles_labels()
        axes[4].legend(lines1 + lines2, labels1 + labels2)
        axes[4].grid(True)

        rotor_spd = np.array([r[f"rotor_spd_T{i}"] for r in results])
        gen_spd   = np.array([r[f"gen_spd_T{i}"]   for r in results])
        axes[5].plot(t_arr, rotor_spd, label="Rotor (rad/s)")
        axes[5].plot(t_arr, gen_spd,   label="Generator (rad/s)", linestyle="--")
        axes[5].set_ylabel("Speed (rad/s)")
        axes[5].set_xlabel("Time (s)")
        axes[5].legend()
        axes[5].grid(True)

        fig.tight_layout()
        _savefig(fig, f"T{i}_io_verification")

    # --- Figure P: T{i} Platform Motion (6 rows: disp / vel / accel, trans then rot) ---
    fig_p, axes_p = plt.subplots(6, 1, figsize=(12, 20), sharex=True)
    fig_p.suptitle(f"FAST.Farm Full IO — T{i} Platform Motion", fontsize=13)

    axes_p[0].plot(t_arr, np.array([r[f"platform_tdx_T{i}"] for r in results]), label="TDX (surge)")
    axes_p[0].plot(t_arr, np.array([r[f"platform_tdy_T{i}"] for r in results]), label="TDY (sway)",  linestyle="--")
    axes_p[0].plot(t_arr, np.array([r[f"platform_tdz_T{i}"] for r in results]), label="TDZ (heave)", linestyle=":")
    axes_p[0].set_ylabel("Trans. disp. (m)")
    axes_p[0].legend()
    axes_p[0].grid(True)

    axes_p[1].plot(t_arr, np.array([r[f"p_tvx_T{i}"] for r in results]), label="TVX (surge)")
    axes_p[1].plot(t_arr, np.array([r[f"p_tvy_T{i}"] for r in results]), label="TVY (sway)",  linestyle="--")
    axes_p[1].plot(t_arr, np.array([r[f"p_tvz_T{i}"] for r in results]), label="TVZ (heave)", linestyle=":")
    axes_p[1].set_ylabel("Trans. vel. (m/s)")
    axes_p[1].legend()
    axes_p[1].grid(True)

    axes_p[2].plot(t_arr, np.array([r[f"p_tax_T{i}"] for r in results]), label="TAX (surge)")
    axes_p[2].plot(t_arr, np.array([r[f"p_tay_T{i}"] for r in results]), label="TAY (sway)",  linestyle="--")
    axes_p[2].plot(t_arr, np.array([r[f"p_taz_T{i}"] for r in results]), label="TAZ (heave)", linestyle=":")
    axes_p[2].set_ylabel("Trans. accel. (m/s²)")
    axes_p[2].legend()
    axes_p[2].grid(True)

    axes_p[3].plot(t_arr, np.array([r[f"platform_rdx_T{i}"] for r in results]), label="RDX (roll)")
    axes_p[3].plot(t_arr, np.array([r[f"platform_rdy_T{i}"] for r in results]), label="RDY (pitch)", linestyle="--")
    axes_p[3].plot(t_arr, np.array([r[f"platform_rdz_T{i}"] for r in results]), label="RDZ (yaw)",   linestyle=":")
    axes_p[3].set_ylabel("Rot. disp. (deg)")
    axes_p[3].legend()
    axes_p[3].grid(True)

    axes_p[4].plot(t_arr, np.array([r[f"p_rvx_T{i}"] for r in results]), label="RVX (roll)")
    axes_p[4].plot(t_arr, np.array([r[f"p_rvy_T{i}"] for r in results]), label="RVY (pitch)", linestyle="--")
    axes_p[4].plot(t_arr, np.array([r[f"p_rvz_T{i}"] for r in results]), label="RVZ (yaw)",   linestyle=":")
    axes_p[4].set_ylabel("Rot. vel. (rad/s)")
    axes_p[4].legend()
    axes_p[4].grid(True)

    axes_p[5].plot(t_arr, np.array([r[f"p_rax_T{i}"] for r in results]), label="RAX (roll)")
    axes_p[5].plot(t_arr, np.array([r[f"p_ray_T{i}"] for r in results]), label="RAY (pitch)", linestyle="--")
    axes_p[5].plot(t_arr, np.array([r[f"p_raz_T{i}"] for r in results]), label="RAZ (yaw)",   linestyle=":")
    axes_p[5].set_ylabel("Rot. accel. (rad/s²)")
    axes_p[5].set_xlabel("Time (s)")
    axes_p[5].legend()
    axes_p[5].grid(True)

    fig_p.tight_layout()
    _savefig(fig_p, f"T{i}_platform")

    # --- Figure I: T{i} Controller Parameters (4 rows) ---
    fig_i, axes_i = plt.subplots(4, 1, figsize=(12, 13), sharex=True)
    fig_i.suptitle(f"FAST.Farm Full IO — T{i} Controller Parameters", fontsize=13)

    axes_i[0].plot(t_arr, np.array([r[f"dem_pwr_T{i}"] for r in results]) / 1e6)
    axes_i[0].set_ylabel("Demanded power (MW)")
    axes_i[0].grid(True)

    axes_i[1].plot(t_arr, np.array([r[f"dem_gs_T{i}"]  for r in results]), label="Demanded")
    axes_i[1].plot(t_arr, np.array([r[f"gs_min_T{i}"]  for r in results]), label="Min opt", linestyle="--")
    axes_i[1].plot(t_arr, np.array([r[f"gs_max_T{i}"]  for r in results]), label="Max opt", linestyle=":")
    axes_i[1].set_ylabel("Gen. speed (rad/s)")
    axes_i[1].legend()
    axes_i[1].grid(True)

    axes_i[2].plot(t_arr, np.array([r[f"dem_gt_T{i}"]  for r in results]) / 1e3, label="Demanded gen torque")
    axes_i[2].set_ylabel("Gen. torque dem. (kN·m)")
    axes_i[2].legend()
    axes_i[2].grid(True)

    axes_i[3].plot(t_arr, np.array([r[f"pt_min_T{i}"]  for r in results]), label="Pitch min")
    axes_i[3].plot(t_arr, np.array([r[f"pt_max_T{i}"]  for r in results]), label="Pitch max", linestyle="--")
    axes_i[3].set_ylabel("Pitch limits (deg)")
    axes_i[3].set_xlabel("Time (s)")
    axes_i[3].legend()
    axes_i[3].grid(True)

    fig_i.tight_layout()
    _savefig(fig_i, f"T{i}_controller")

# --- Wind measurements: all turbines on one figure ---
turb_colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
fig_wind, axes_w = plt.subplots(2, 1, figsize=(10, 5), sharex=True)
fig_wind.suptitle("Wind Measurements (per turbine)", fontsize=13)
for i in range(n_turbines):
    col = turb_colors[i % len(turb_colors)]
    axes_w[0].plot(t_arr, np.array([r[f"wind_spd_T{i}"] for r in results]), label=f"T{i}", color=col)
    axes_w[1].plot(t_arr, np.array([r[f"wind_dir_T{i}"] for r in results]), label=f"T{i}", color=col)
axes_w[0].set_ylabel("Wind speed (m/s)")
axes_w[0].legend()
axes_w[0].grid(True)
axes_w[1].set_ylabel("Wind direction (deg)")
axes_w[1].set_xlabel("Time (s)")
axes_w[1].legend()
axes_w[1].grid(True)
fig_wind.tight_layout()
_savefig(fig_wind, "wind")

# --- Yaw dashboard: 2×2 layout matching physical farm positions ---
# Farm layout (from 2x2.fstf): wind flows in +X direction
#   row 0 (top,    Y=630): T2 (upstream)  | T3 (downstream)
#   row 1 (bottom, Y=0  ): T0 (upstream)  | T1 (downstream)
turb_to_ax = {0: (1, 0), 1: (1, 1), 2: (0, 0), 3: (0, 1)}
fig_yaw, axes_yaw = plt.subplots(2, 2, figsize=(14, 8), sharex=True)
fig_yaw.suptitle("Yaw Dashboard — wind dir / nacelle yaw / platform rdz / error (per turbine)", fontsize=13)

for i in range(n_turbines):
    row, col = turb_to_ax[i]
    ax = axes_yaw[row][col]

    wind_dir = np.array([r[f"wind_dir_T{i}"]      for r in results]) - 270         # convert to 0°=from left, +CCW
    yaw_meas = np.array([r[f"yaw_T{i}"]           for r in results])
    rdz      = np.array([r[f"platform_rdz_T{i}"]  for r in results])
    # error    = np.array([r.get(f"yaw_error_T{i}", np.nan) for r in results])

    ax.plot(t_arr, wind_dir, label="Wind dir (deg)",    color="steelblue")
    ax.plot(t_arr, yaw_meas, label="Nacelle yaw (deg)", color="darkorange",  linestyle="--")
    ax.plot(t_arr, rdz,      label="Platform rdz (deg)",color="tab:green",   linestyle=":")
    # ax.plot(t_arr, error,    label="Error (deg)",        color="tab:red",     linestyle="-.")
    ax.set_title(f"T{i}  (row={row}, col={col})")
    ax.set_ylabel("Angle (deg)")
    if row == 1:
        ax.set_xlabel("Time (s)")
    ax.legend(fontsize=7)
    ax.grid(True)

fig_yaw.tight_layout()
_savefig(fig_yaw, "yaw_dashboard")
