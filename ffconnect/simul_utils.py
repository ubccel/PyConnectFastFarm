import os
import shutil
import warnings
from pathlib import Path

from openfast_toolbox.io.fast_input_file import FASTInputFile

LOCAL_DIR = Path(__file__).resolve().parent

SERVO_DIR = str(LOCAL_DIR / "simulator/{}/servo_dll/") + "/"


def read_simul_info(fstf_file):
    fstf = FASTInputFile(fstf_file)
    dt = fstf["DT_Low"]
    num_iter = int(fstf["TMax"] // dt)
    num_turbines = fstf["NumTurbines"]
    return num_turbines, num_iter, dt


def get_inflow_file_path(fstf_file):
    fstf = FASTInputFile(fstf_file)
    inflow_file_name = fstf["InflowFile"].replace('"', "")
    inflow_file_path = (Path(fstf_file).parent / inflow_file_name).resolve()
    return inflow_file_path


def read_inflow_info(inflow_file):
    inflow = FASTInputFile(inflow_file)
    return inflow["HWindSpeed"]


def write_inflow_info(inflow_file, wind_speed):
    inflow = FASTInputFile(inflow_file)
    inflow["HWindSpeed"] = wind_speed
    inflow.write(os.path.join(inflow_file))
    return inflow_file


def create_dll(fstf_file):
    fstf = FASTInputFile(fstf_file)
    base = Path(fstf_file).parent
    path_to_sc_dll = (base / fstf["SC_FileName"].replace('"', "")).resolve()

    # copy SC DLL only if it does not exist !
    if path_to_sc_dll.exists():
        warnings.warn(
            f"A supercontroler DLL already exists in {path_to_sc_dll}."
            "It will not be replaced."
        )
    else:
        path_to_sc_dll.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(f"{SERVO_DIR.format('fastfarm')}/SC_DLL.dll", path_to_sc_dll)

    for ref_path in fstf["WindTurbines"][:, 3]:
        fst = FASTInputFile((base / ref_path.replace('"', "")).resolve())
        servo_file_name = fst["ServoFile"]
        servo = FASTInputFile((base / servo_file_name.replace('"', "")).resolve())
        servo_dll_filename = servo["DLL_FileName"]
        path_to_servo_dll = (base / servo_dll_filename.replace('"', "")).resolve()
        # copy SC DLL only if it does not exist !
        if path_to_servo_dll.exists():
            warnings.warn(
                f"A controler DLL already exists in {path_to_servo_dll}"
                "It will not be replaced."
            )
        else:
            shutil.copy(
                f'{SERVO_DIR.format("fastfarm")}/DISCON_WT1.dll', path_to_servo_dll
            )

def reset_simul_file(simul_file, it):
    new_path = path = Path(simul_file)
    if it > 0:
        new_path = path.with_stem(f"{path.stem}_iter{it}")
        shutil.copy2(path, new_path)
    return str(new_path)
