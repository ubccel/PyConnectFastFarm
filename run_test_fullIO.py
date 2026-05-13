# Run with: mpiexec -n 1 python run_test_fullIO.py
'''
    Test the full IO (SC_DLL_Full variant, NumCtrl2SC=69) in ffconnect
    1) Ensure all 69 IO variables are available and sensible
    2) Ensure that controls (yaw, IPC) do not interfere with uncontrolled channels
    3) Plot all variables to verify correctness

    Specific tasks:
    1) Run a simple FAST.Farm simulation and retrieve all IO variables
        * floating FOWF (3 turbines, OC4 semi-submersible)
        * fixed-bottom onshore (2 turbines)
    2) Apply control and verify results
        * yaw
        * IPC
    3) Plot all input/output groups
'''

import pickle
import numpy as np
import matplotlib.pyplot as plt
from ffconnect.interface import FastFarmInterface

# ================================= Initialization =================================
save_results = False
print_result = False
IO_check = True
Load_check = False
Additional_check = False
# --- User-defined paths ---
FFexePath = "D:\\2_PhD_UBC\\Code\\FASTv355\\FAST.Farm_x64_OMP_v355.exe"
# FFsimPath = "D:\\2_PhD_UBC\\Code\\FASTv355\\SteadyWind_FOWF_ffconnect_full\\FAST.Farm.fstf"  # floating (3T)
FFsimPath = "D:\\2_PhD_UBC\\Code\\FASTv355\\SteadyWind_ffconnect_full\\FAST.Farm.fstf"  # fixed-bottom (2T)
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

# --- Simulation loop ---
results = []
done = False

for t in range(max_iter):
    if t >= activate_step:
        interface.set_command(
            yaw=yaw_schedule[t],
            ipc=None,
            torque=None, # torque_schedule[t] if torque_schedule[t] > 0 else None
            turb_idx=0,
        )
        interface.set_command(
            yaw=yaw_schedule[t] * -1,
            ipc=None,
            torque=None,
            turb_idx=1,
        )
        # This is only for testing (known that only maximal 3 turbines)
        if n_turbines > 2:
            interface.set_command(
                yaw=None,
                ipc=None,
                torque=None,
                turb_idx=2,
            )
    done = interface.step()

    step_result = {"t": t * dt}
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
        if t >= activate_step:
            print(
                f"t={t*dt:6.1f}s  power={total_power/1e6:.3f} MW  "
                f"pitch_T0=[{step_result['pitch_b1_T0']:.2f}, "
                f"{step_result['pitch_b2_T0']:.2f}, "
                f"{step_result['pitch_b3_T0']:.2f}] deg"
            )
        else:
            print(f"t={t*dt:6.1f}s  power={total_power/1e6:.3f} MW  (warmup)")

    if done:
        break

# ================================= Save Results =================================
if save_results:
    with open("results_test_full.pkl", "wb") as f:
        pickle.dump(results, f)
    print(f"Results saved to results_test_full.pkl ({len(results)} steps)")

# ================================= Plotting =================================
t_arr = np.array([r["t"] for r in results])
blade_colors = ["tab:green", "tab:red", "tab:purple"]
blade_labels = ["Blade 1", "Blade 2", "Blade 3"]
oop_labels   = ["OOP Blade 1", "OOP Blade 2", "OOP Blade 3"]
ip_labels    = ["IP Blade 1",  "IP Blade 2",  "IP Blade 3"]

for i in range(n_turbines):
    if IO_check:
        # --- Figure A: T{i} I/O Verification (8 rows) ---
        fig, axes = plt.subplots(8, 1, figsize=(12, 26), sharex=True)
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

        tdx = np.array([r[f"platform_tdx_T{i}"] for r in results])
        tdy = np.array([r[f"platform_tdy_T{i}"] for r in results])
        tdz = np.array([r[f"platform_tdz_T{i}"] for r in results])
        axes[5].plot(t_arr, tdx, linestyle="-",  label="TDX (surge)")
        axes[5].plot(t_arr, tdy, linestyle="--", label="TDY (sway)")
        axes[5].plot(t_arr, tdz, linestyle=":",  label="TDZ (heave)")
        axes[5].set_ylabel("Platform trans. (m)")
        axes[5].legend()
        axes[5].grid(True)

        rdx = np.array([r[f"platform_rdx_T{i}"] for r in results])
        rdy = np.array([r[f"platform_rdy_T{i}"] for r in results])
        rdz = np.array([r[f"platform_rdz_T{i}"] for r in results])
        axes[6].plot(t_arr, rdx, linestyle="-",  label="RDX (roll)")
        axes[6].plot(t_arr, rdy, linestyle="--", label="RDY (pitch)")
        axes[6].plot(t_arr, rdz, linestyle=":",  label="RDZ (yaw)")
        axes[6].set_ylabel("Platform rot. (deg)")
        axes[6].legend()
        axes[6].grid(True)

        rotor_spd = np.array([r[f"rotor_spd_T{i}"] for r in results])
        gen_spd   = np.array([r[f"gen_spd_T{i}"]   for r in results])
        axes[7].plot(t_arr, rotor_spd, label="Rotor (rad/s)")
        axes[7].plot(t_arr, gen_spd,   label="Generator (rad/s)", linestyle="--")
        axes[7].set_ylabel("Speed (rad/s)")
        axes[7].set_xlabel("Time (s)")
        axes[7].legend()
        axes[7].grid(True)

        fig.tight_layout()

    if Additional_check:
        # --- Figure C: T{i} Structural / Additional Variables (3 rows) ---
        fig_c, axes_c = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
        fig_c.suptitle(f"FAST.Farm Full IO — T{i} Structural Variables", fontsize=13)

        fa_acc = np.array([r[f"tower_fa_T{i}"] for r in results])
        ss_acc = np.array([r[f"tower_ss_T{i}"] for r in results])
        axes_c[0].plot(t_arr, fa_acc, label="Fore-aft (m/s²)")
        axes_c[0].plot(t_arr, ss_acc, label="Side-side (m/s²)", linestyle="--")
        axes_c[0].set_ylabel("Tower accel. (m/s²)")
        axes_c[0].legend()
        axes_c[0].grid(True)

        azimuth = np.array([r[f"azimuth_T{i}"] for r in results])
        axes_c[1].plot(t_arr, azimuth, color="tab:olive")
        axes_c[1].set_ylabel("Azimuth (deg)")
        axes_c[1].grid(True)

        torque_c = np.array([r[f"torque_T{i}"] for r in results]) / 1e3
        axes_c[2].plot(t_arr, torque_c, color="tab:brown")
        axes_c[2].set_ylabel("Gen. torque (kN·m)")
        axes_c[2].set_xlabel("Time (s)")
        axes_c[2].grid(True)

        fig_c.tight_layout()

        # --- Figure D: T{i} Shaft Loads (5 rows) ---
        fig_d, axes_d = plt.subplots(5, 1, figsize=(12, 16), sharex=True)
        fig_d.suptitle(f"FAST.Farm Full IO — T{i} Shaft Loads", fontsize=13)

        axes_d[0].plot(t_arr, np.array([r[f"shaft_pwr_T{i}"] for r in results]) / 1e6)
        axes_d[0].set_ylabel("Shaft power (MW)")
        axes_d[0].grid(True)

        axes_d[1].plot(t_arr, np.array([r[f"sh_torq_T{i}"] for r in results]) / 1e3)
        axes_d[1].set_ylabel("Shaft torque (kN·m)")
        axes_d[1].grid(True)

        axes_d[2].plot(t_arr, np.array([r[f"sh_thr_T{i}"] for r in results]) / 1e3)
        axes_d[2].set_ylabel("Shaft thrust (kN)")
        axes_d[2].grid(True)

        axes_d[3].plot(t_arr, np.array([r[f"sh_fy_T{i}"] for r in results]) / 1e3, label="Fy")
        axes_d[3].plot(t_arr, np.array([r[f"sh_fz_T{i}"] for r in results]) / 1e3, label="Fz", linestyle="--")
        axes_d[3].set_ylabel("Shaft force Y/Z (kN)")
        axes_d[3].legend()
        axes_d[3].grid(True)

        rotor_avg = np.array([r[f"rotor_avg_T{i}"] for r in results])
        axes_d[4].plot(t_arr, rotor_avg, color="steelblue")
        axes_d[4].set_ylabel("Rotor avg wind (m/s)")
        axes_d[4].set_xlabel("Time (s)")
        axes_d[4].grid(True)

        fig_d.tight_layout()

        # --- Figure E: T{i} Hub & Yaw Bearing Moments (4 rows) ---
        fig_e, axes_e = plt.subplots(4, 1, figsize=(12, 13), sharex=True)
        fig_e.suptitle(f"FAST.Farm Full IO — T{i} Hub & Yaw Bearing Moments", fontsize=13)

        axes_e[0].plot(t_arr, np.array([r[f"hub_myr_T{i}"] for r in results]) / 1e6, label="My rotating")
        axes_e[0].plot(t_arr, np.array([r[f"hub_mzr_T{i}"] for r in results]) / 1e6, label="Mz rotating", linestyle="--")
        axes_e[0].set_ylabel("Hub moment\nrotating (MN·m)")
        axes_e[0].legend()
        axes_e[0].grid(True)

        axes_e[1].plot(t_arr, np.array([r[f"hub_myf_T{i}"] for r in results]) / 1e6, label="My fixed")
        axes_e[1].plot(t_arr, np.array([r[f"hub_mzf_T{i}"] for r in results]) / 1e6, label="Mz fixed", linestyle="--")
        axes_e[1].set_ylabel("Hub moment\nfixed (MN·m)")
        axes_e[1].legend()
        axes_e[1].grid(True)

        axes_e[2].plot(t_arr, np.array([r[f"yb_my_T{i}"] for r in results]) / 1e6)
        axes_e[2].set_ylabel("Yaw bearing My\n(MN·m)")
        axes_e[2].grid(True)

        axes_e[3].plot(t_arr, np.array([r[f"yb_mz_T{i}"] for r in results]) / 1e6)
        axes_e[3].set_ylabel("Yaw bearing Mz\n(MN·m)")
        axes_e[3].set_xlabel("Time (s)")
        axes_e[3].grid(True)

        fig_e.tight_layout()

        # --- Figure F: T{i} Nacelle IMU Angular Accelerations (3 rows) ---
        fig_f, axes_f = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
        fig_f.suptitle(f"FAST.Farm Full IO — T{i} Nacelle IMU Angular Accelerations", fontsize=13)

        axes_f[0].plot(t_arr, np.array([r[f"nc_roll_T{i}"] for r in results]))
        axes_f[0].set_ylabel("Roll accel. (rad/s²)")
        axes_f[0].grid(True)

        axes_f[1].plot(t_arr, np.array([r[f"nc_nod_T{i}"] for r in results]))
        axes_f[1].set_ylabel("Nodding accel. (rad/s²)")
        axes_f[1].grid(True)

        axes_f[2].plot(t_arr, np.array([r[f"nc_yaw_T{i}"] for r in results]))
        axes_f[2].set_ylabel("Yaw accel. (rad/s²)")
        axes_f[2].set_xlabel("Time (s)")
        axes_f[2].grid(True)

        fig_f.tight_layout()

        # --- Figure G: T{i} Platform Velocities (2 rows) ---
        fig_g, axes_g = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
        fig_g.suptitle(f"FAST.Farm Full IO — T{i} Platform Velocities", fontsize=13)

        axes_g[0].plot(t_arr, np.array([r[f"p_tvx_T{i}"] for r in results]), label="TVX (surge)")
        axes_g[0].plot(t_arr, np.array([r[f"p_tvy_T{i}"] for r in results]), label="TVY (sway)", linestyle="--")
        axes_g[0].plot(t_arr, np.array([r[f"p_tvz_T{i}"] for r in results]), label="TVZ (heave)", linestyle=":")
        axes_g[0].set_ylabel("Trans. velocity (m/s)")
        axes_g[0].legend()
        axes_g[0].grid(True)

        axes_g[1].plot(t_arr, np.array([r[f"p_rvx_T{i}"] for r in results]), label="RVX (roll)")
        axes_g[1].plot(t_arr, np.array([r[f"p_rvy_T{i}"] for r in results]), label="RVY (pitch)", linestyle="--")
        axes_g[1].plot(t_arr, np.array([r[f"p_rvz_T{i}"] for r in results]), label="RVZ (yaw)", linestyle=":")
        axes_g[1].set_ylabel("Rot. velocity (rad/s)")
        axes_g[1].set_xlabel("Time (s)")
        axes_g[1].legend()
        axes_g[1].grid(True)

        fig_g.tight_layout()

        # --- Figure H: T{i} Platform Accelerations (2 rows) ---
        fig_h, axes_h = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
        fig_h.suptitle(f"FAST.Farm Full IO — T{i} Platform Accelerations", fontsize=13)

        axes_h[0].plot(t_arr, np.array([r[f"p_tax_T{i}"] for r in results]), label="TAX (surge)")
        axes_h[0].plot(t_arr, np.array([r[f"p_tay_T{i}"] for r in results]), label="TAY (sway)", linestyle="--")
        axes_h[0].plot(t_arr, np.array([r[f"p_taz_T{i}"] for r in results]), label="TAZ (heave)", linestyle=":")
        axes_h[0].set_ylabel("Trans. accel. (m/s²)")
        axes_h[0].legend()
        axes_h[0].grid(True)

        axes_h[1].plot(t_arr, np.array([r[f"p_rax_T{i}"] for r in results]), label="RAX (roll)")
        axes_h[1].plot(t_arr, np.array([r[f"p_ray_T{i}"] for r in results]), label="RAY (pitch)", linestyle="--")
        axes_h[1].plot(t_arr, np.array([r[f"p_raz_T{i}"] for r in results]), label="RAZ (yaw)", linestyle=":")
        axes_h[1].set_ylabel("Rot. accel. (rad/s²)")
        axes_h[1].set_xlabel("Time (s)")
        axes_h[1].legend()
        axes_h[1].grid(True)

        fig_h.tight_layout()

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

        # --- Figure J: T{i} Constants & Flags (4 rows) ---
        fig_j, axes_j = plt.subplots(4, 1, figsize=(12, 13), sharex=True)
        fig_j.suptitle(f"FAST.Farm Full IO — T{i} Constants & Flags", fontsize=13)

        axes_j[0].plot(t_arr, np.array([r[f"air_den_T{i}"] for r in results]))
        axes_j[0].set_ylabel("Air density (kg/m³)")
        axes_j[0].grid(True)

        axes_j[1].plot(t_arr, np.array([r[f"rotor_avg_T{i}"] for r in results]))
        axes_j[1].set_ylabel("Rotor avg wind (m/s)")
        axes_j[1].grid(True)

        axes_j[2].plot(t_arr, np.array([r[f"dll_dt_T{i}"]  for r in results]))
        axes_j[2].set_ylabel("DLL DT (s)")
        axes_j[2].grid(True)

        axes_j[3].plot(t_arr, np.array([r[f"pt_mode_T{i}"]  for r in results]), label="Pitch ctrl mode")
        axes_j[3].plot(t_arr, np.array([r[f"yaw_mode_T{i}"] for r in results]), label="Yaw ctrl mode", linestyle="--")
        axes_j[3].plot(t_arr, np.array([r[f"n_blades_T{i}"] for r in results]), label="Num blades", linestyle=":")
        axes_j[3].set_ylabel("Flags / counts")
        axes_j[3].set_xlabel("Time (s)")
        axes_j[3].legend()
        axes_j[3].grid(True)

        fig_j.tight_layout()

    if Load_check:
        # --- Figure B: T{i} Blade Root Bending Moments (6 rows) ---
        fig2, axes2 = plt.subplots(6, 1, figsize=(12, 18), sharex=True)
        fig2.suptitle(f"FAST.Farm Full IO Test — T{i} Blade Root Bending Moments", fontsize=13)

        for row, (idx, label) in enumerate(
            [(0, oop_labels[0]), (1, oop_labels[1]), (2, oop_labels[2]),
             (3,  ip_labels[0]), (4,  ip_labels[1]), (5,  ip_labels[2])]
        ):
            loads = np.array([r[f"loads_T{i}"][idx] for r in results]) / 1e6
            axes2[row].plot(t_arr, loads)
            axes2[row].set_ylabel(f"{label}\n(MN·m)")
            axes2[row].grid(True)

        axes2[-1].set_xlabel("Time (s)")
        fig2.tight_layout()

plt.show()
