"""
ffcase_check.py  —  FAST.Farm parameter checker

Reads a FAST.Farm .fstf file and validates key hyperparameters against
the OpenFAST Model Guidance (fastFarmBoxExtent formulas).

Reference: https://github.com/OpenFAST/python-toolbox/tree/main/pyFAST/fastfarm

Usage:
    python ffcase_check.py path/to/FAST.Farm.fstf                           # single case, default turbine params
    python ffcase_check.py path/to/FAST.Farm.fstf D hub_height U            # single case, custom params
"""

import math
import sys
from pathlib import Path
from openfast_toolbox.io.fast_input_file import FASTInputFile

# --- pyFAST / OpenFAST Model Guidance constants ---
CMEANDER         = 1.9    # wake-meandering calibration coefficient
EXTENT_X         = 1.1    # high-res box X-extent in rotor diameters
EXTENT_YZ        = 1.1    # high-res box YZ-extent in rotor diameters
EXTENT_WAKE      = 8.0    # low-res downstream padding beyond last turbine (D)
SAFETY_NUMPLANES = 1.15   # 15% buffer on minimum NumPlanes
ALIGN_TOL        = 0.02   # max fractional deviation from integer for alignment check


def check_case(fstf_path: str,
               D: float = 126.0,
               hub_height: float = 90.0,
               U: float = 9.93) -> dict:
    """
    Read one .fstf file and run all parameter checks.

    Parameters
    ----------
    fstf_path   : path to FAST.Farm .fstf input file
    D           : rotor diameter (m)          default = 126 m  (NREL 5MW)
    hub_height  : hub height above MSL (m)    default = 90 m   (NREL 5MW / OC4 semi-sub)
    U           : mean hub-height wind speed  default = 9.93 m/s

    Returns
    -------
    dict  {check_name: (status, actual, expected, message)}
          status ∈ {'PASS', 'WARN', 'FAIL', 'INFO'}
    """
    fstf = FASTInputFile(fstf_path)
    R = D / 2.0

    # --- scalar grid parameters ---
    DT_Low   = float(fstf["DT_Low"])
    dX_Low   = float(fstf["dX_Low"]);  NX_Low = int(fstf["NX_Low"]);  X0_Low = float(fstf["X0_Low"])
    dY_Low   = float(fstf["dY_Low"]);  NY_Low = int(fstf["NY_Low"]);  Y0_Low = float(fstf["Y0_Low"])
    dZ_Low   = float(fstf["dZ_Low"]);  NZ_Low = int(fstf["NZ_Low"]);  Z0_Low = float(fstf["Z0_Low"])
    NumPlanes = int(fstf["NumPlanes"])
    dr        = float(fstf["dr"])
    NumRadii  = int(fstf["NumRadii"])
    NX_High   = int(fstf["NX_High"])
    NY_High   = int(fstf["NY_High"])
    NZ_High   = int(fstf["NZ_High"])

    # --- per-turbine table: WT_X WT_Y WT_Z FASTInFile X0_High Y0_High Z0_High dX_High dY_High dZ_High ---
    wt = fstf["WindTurbines"]
    xWT     = [float(row[0]) for row in wt]
    yWT     = [float(row[1]) for row in wt]
    zWT     = [float(row[2]) for row in wt]
    x0_high = [float(row[4]) for row in wt]
    y0_high = [float(row[5]) for row in wt]
    z0_high = [float(row[6]) for row in wt]
    dx_high = [float(row[7]) for row in wt]
    dy_high = [float(row[8]) for row in wt]
    dz_high = [float(row[9]) for row in wt]

    results = {}

    # ======== Check low resolution discretization and coverage
    # 1. Spatial coveragancee of low-res domain (must cover all turbines + wake region)
    # X coverage (must reach the farthest turbine)
    X_max_low = X0_Low + (NX_Low - 1) * dX_Low
    xWT_max   = max(xWT)
    status = "PASS" if X_max_low >= xWT_max else "FAIL"
    results["low_res_X_coverage"] = (
        status, X_max_low, xWT_max,
        f"X_max_low={X_max_low:.1f} m  vs  farthest_turbine_X={xWT_max:.1f} m",
    )
    # Y coverage (must span all rotor disks laterally)
    Y_max_low = Y0_Low + (NY_Low - 1) * dY_Low
    y_need_min = min(yWT) - R
    y_need_max = max(yWT) + R
    ok_Y = (Y0_Low <= y_need_min) and (Y_max_low >= y_need_max)
    status = "PASS" if ok_Y else "FAIL"
    results["low_res_Y_coverage"] = (
        status, (Y0_Low, Y_max_low), (y_need_min, y_need_max),
        f"Y_low=[{Y0_Low:.1f}, {Y_max_low:.1f}] m  must contain  "
        f"[{y_need_min:.1f}, {y_need_max:.1f}] m",
    )
    # Z coverage (must reach rotor tip above hub)
    Z_max_low = Z0_Low + (NZ_Low - 1) * dZ_Low
    Z_need    = hub_height + R
    status = "PASS" if Z_max_low >= Z_need else "FAIL"
    results["low_res_Z_coverage"] = (
        status, Z_max_low, Z_need,
        f"Z_max_low={Z_max_low:.1f} m  must be >=  hub+R={Z_need:.1f} m",
    )
    # 2. Temporal discretization of low-res domain
    # dX_Low vs pyFAST guideline  (finer than guideline is acceptable)
    dX_Low_desired = CMEANDER * D * U / 150.0
    status = "PASS" if dX_Low <= dX_Low_desired * 1.05 else "WARN"
    results["dX_Low_guideline"] = (
        status, dX_Low, dX_Low_desired,
        f"actual={dX_Low} m, pyFAST_guideline={dX_Low_desired:.2f} m  "
        f"[Cmeander*D*U/150]",
    )
    # dX_Low must be an integer multiple of dX_High and dX_Low should be lower or equal to dX_High
    dX_High_ref = dx_high[0]
    ratio = dX_Low / dX_High_ref
    status = "PASS" if (abs(ratio - round(ratio)) < 0.001) and (dX_Low <= dX_High_ref) else "FAIL"
    results["dX_Low_multiple_of_dX_High"] = (
        status, dX_Low, dX_High_ref,
        f"dX_Low/dX_High = {dX_Low}/{dX_High_ref} = {ratio:.4f}  (must be integer)",
    )
    # DT_Low vs pyFAST wake-physics recommendation (INFO only — control use intentionally smaller)
    DT_Low_rec = CMEANDER * D / (10.0 * U)
    results["DT_Low_wake_physics"] = (
        "INFO", DT_Low, DT_Low_rec,
        f"actual={DT_Low} s,  pyFAST_wake_guideline={DT_Low_rec:.3f} s  "
        f"[Cmeander*D/(10*U)]  — smaller DT_Low is fine for control research",
    )

    # ======== Check high resolution discretization and coverage
    # Per-turbine: high-res rotor coverage
    for i, (x_wt, y_wt, x0h, y0h, z0h, dxh, dyh, dzh) in enumerate(
        zip(xWT, yWT, x0_high, y0_high, z0_high, dx_high, dy_high, dz_high)
    ):
        x_end_h = x0h + (NX_High - 1) * dxh
        y_end_h = y0h + (NY_High - 1) * dyh
        z_end_h = z0h + (NZ_High - 1) * dzh

        ok_x = (x0h <= x_wt - R) and (x_end_h >= x_wt + R)
        ok_y = (y0h <= y_wt - R) and (y_end_h >= y_wt + R)
        ok_z = (z0h <= hub_height - R) and (z_end_h >= hub_height + R)
        status = "PASS" if (ok_x and ok_y and ok_z) else "FAIL"
        results[f"high_res_rotor_coverage_T{i+1}"] = (
            status,
            (x0h, x_end_h, y0h, y_end_h, z0h, z_end_h),
            (x_wt - R, x_wt + R, y_wt - R, y_wt + R, hub_height - R, hub_height + R),
            f"T{i+1} HR X=[{x0h:.1f},{x_end_h:.1f}]  Y=[{y0h:.1f},{y_end_h:.1f}]  "
            f"Z=[{z0h:.1f},{z_end_h:.1f}]  "
            f"rotor_needs X=[{x_wt-R:.1f},{x_wt+R:.1f}]  "
            f"Y=[{y_wt-R:.1f},{y_wt+R:.1f}]  "
            f"Z=[{hub_height-R:.1f},{hub_height+R:.1f}]",
        )
        ## Check for grid alignment
        # frac_x = (x0h - X0_Low) / dxh
        # frac_y = (y0h - Y0_Low) / dyh
        # ok_ax  = abs(frac_x - round(frac_x)) < ALIGN_TOL
        # ok_ay  = abs(frac_y - round(frac_y)) < ALIGN_TOL
        # status = "PASS" if (ok_ax and ok_ay) else "FAIL"
        # results[f"alignment_T{i+1}"] = (
        #     status,
        #     (frac_x, frac_y),
        #     (round(frac_x), round(frac_y)),
        #     f"T{i+1}  (X0_High-X0_Low)/dX_High={frac_x:.4f}  "
        #     f"(Y0_High-Y0_Low)/dY_High={frac_y:.4f}  (both must be integers)",
        # )

    # ======== Check wake model parameters
    # NumPlanes sufficiency
    max_sep = max(xWT) - min(xWT)
    if max_sep > 0:
        np_min = math.ceil(max_sep / (U * DT_Low)) * SAFETY_NUMPLANES
        status = "PASS" if NumPlanes >= np_min else "FAIL"
    else:
        np_min = 0
        status = "PASS"
    results["NumPlanes"] = (
        status, NumPlanes, np_min,
        f"actual={NumPlanes}, need>={np_min:.1f}  "
        f"[sep={max_sep:.0f} m, U={U} m/s, DT_Low={DT_Low} s]",
    )
    # NumRadii must reach rotor tip
    NumRadii_min = 3*D / (2*dr) + 1
    status = "PASS" if NumRadii >= NumRadii_min else "FAIL"
    results["NumRadii_coverage"] = (
        status, NumRadii, NumRadii_min,
        f"NumRadii*dr = {NumRadii}*{dr} = {NumRadii*dr:.1f} m  must be >= {NumRadii_min:.1f} m",
    )

    return results


def _print_results(case_name: str, results: dict) -> None:
    TAG = {"PASS": "  PASS", "WARN": "  WARN", "FAIL": "**FAIL", "INFO": "  INFO"}
    print(f"\n{'='*70}")
    print(f"  Case: {case_name}")
    print(f"{'='*70}")
    any_fail = False
    for check_name, (status, actual, expected, msg) in results.items():
        tag = TAG.get(status, status)
        print(f"  [{tag}]  {check_name}")
        print(f"           {msg}")
        if status == "FAIL":
            any_fail = True
    overall = "FAIL" if any_fail else "PASS"
    print(f"\n  Overall: {overall}")


if __name__ == "__main__":
    _SCRIPT_DIR = Path(__file__).resolve().parent

    if len(sys.argv) == 2:
        results = check_case(sys.argv[1])
        _print_results(Path(sys.argv[1]).parent.name, results)
    elif len(sys.argv) == 5:
        results = check_case(sys.argv[1],
                             D=float(sys.argv[2]),
                             hub_height=float(sys.argv[3]),
                             U=float(sys.argv[4]))
        _print_results(Path(sys.argv[1]).parent.name, results)