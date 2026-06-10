import platform
import time
import warnings
from abc import ABC
from pathlib import Path
from typing import Dict, Iterable, List, Union

import numpy as np
import pandas as pd
from mpi4py import MPI

from ffconnect.simul_utils import (
    create_dll,
    get_inflow_file_path,
    read_inflow_info,
    read_simul_info,
    reset_simul_file,
    write_inflow_info,
)


class BaseInterface(ABC):
    def __init__(self):
        self.num_turbines = None

    @property
    def wind_speed(self):
        pass

    @property
    def wind_dir(self):
        pass

    def set_yaw_angles(self, yaws: List):
        pass

    def get_yaw_angles(self) -> List:
        pass

    def avg_powers(self) -> List:
        pass

    def init(self):
        pass

    def next_wind(self):
        pass


class PowerBuffer:
    def __init__(self, num_turbines: int, size: int = 50_000, agg: str = np.mean):
        self._agg_fn = agg
        self._size = size
        self.pos = -1
        self._buffer = np.zeros((self._size, num_turbines))

    def add(self, measure: np.array):
        if self.pos < self._size - 1:
            self.pos += 1
        else:
            self._buffer = np.roll(self._buffer, -1, axis=0)

        self._buffer[self.pos, :] = measure

    def get_last(self):
        return self._buffer[self.pos, :]

    def get_all(self, window: int = 1):
        start = self.pos - window if self.pos > window else 0
        return self._buffer[start : self.pos + 1, :]

    def get_agg(self, window: int = 1):
        start = self.pos - window if self.pos > window else 0
        return self._agg_fn(self._buffer[start : self.pos + 1, :], 0)

    def empty(self):
        self._buffer[:] = 0.0
        self.pos = -1


class MPI_Interface(BaseInterface):
    CONTROL_SET = ["yaw", "pitch", "torque"]
    YAW_TAG = 1
    PITCH_TAG = 2
    TORQUE_TAG = 3
    COM_TAG = 0
    MEASURES_TAG = 4
    IPC_TAG = 5

    def __init__(
        self,
        measure_map: dict,
        num_turbines: int,
        buffer_size: int = 50_000,
        log_file: str = None,
        comm: MPI.Comm = MPI.COMM_WORLD,
        target_process_rank: int = None,
        max_iter: int = 500,
        default_avg_window: int = 1,
        per_turbine_flags: bool = False,
    ):
        super().__init__()

        # Check communication channels
        self._comm = comm
        if target_process_rank is None:
            rank = self._comm.Get_rank()
            target_process_rank = 1 - rank
        self._target_process_rank = target_process_rank
        self._buffer_size = buffer_size
        self._default_avg_window = default_avg_window
        self._num_measures = None
        self.current_measures = None
        self.max_iter = max_iter
        self._per_turbine_flags = per_turbine_flags

        # Validate measure map and store names of measure in array
        self._validate_measure_map(measure_map)
        self.num_turbines = num_turbines
        self._power_buffers = PowerBuffer(self.num_turbines, size=self._buffer_size)
        self._wind_buffers = PowerBuffer(2, size=self._buffer_size)
        if per_turbine_flags:
            self._current_yaw_command = np.zeros(2 * num_turbines, dtype=np.double)
            self._current_pitch_command = np.zeros(2 * num_turbines, dtype=np.double)
            self._current_torque_command = np.zeros(2 * num_turbines, dtype=np.double)
            self._current_ipc_command = np.zeros(4 * num_turbines, dtype=np.double)
        else:
            self._current_yaw_command = np.zeros(num_turbines + 1, dtype=np.double)
            self._current_pitch_command = np.zeros(num_turbines + 1, dtype=np.double)
            self._current_torque_command = np.zeros(num_turbines + 1, dtype=np.double)
            self._current_ipc_command = np.zeros(3 * num_turbines + 1, dtype=np.double)
        self._num_iter = 0

        self._logging = False
        if log_file is not None:
            self._log_file = log_file
            self._logging = True

    @property
    def wind_speed(self):
        return self.avg_wind()[0]

    @property
    def wind_dir(self):
        return self.avg_wind()[1]

    def _validate_measure_map(self, measure_map):
        inv_measure_map = {}
        for name, indice in measure_map.items():
            if isinstance(indice, int):
                inv_measure_map[indice] = name
            elif isinstance(indice, Iterable):
                for j, indice_i in enumerate(indice):
                    inv_measure_map[indice_i] = f"{name}_{j}"

        assert min(inv_measure_map.keys()) == 0
        assert max(inv_measure_map.keys()) == len(inv_measure_map) - 1
        measure_names = list(inv_measure_map.values())
        self.measure_map = measure_map
        self.measure_names = measure_names

    def set_command(
        self,
        yaw: float = None,
        pitch: float = None,
        torque: float = None,
        ipc=None,
        turb_idx: int = None,
    ):
        """Set command for a single turbine without advancing the simulation.

        Args:
            yaw: Yaw angle in degrees for the specified turbine.
            pitch: Collective pitch angle in degrees for the specified turbine.
            torque: Generator torque in N-m for the specified turbine.
            ipc: Individual pitch control offsets in degrees, array-like of 3
                 values (one per blade). Superimposed on top of CPC.
            turb_idx: 0-based turbine index.
        """
        assert self.current_measures is not None, "Call `init` before `set_command`"
        assert turb_idx is not None, "`turb_idx` is required for `set_command`"
        assert 0 <= turb_idx < self.num_turbines, (
            f"turb_idx={turb_idx} out of range [0, {self.num_turbines})"
        )
        if self._per_turbine_flags:
            if yaw is not None:
                self._current_yaw_command[2 * turb_idx] = 1.0
                self._current_yaw_command[2 * turb_idx + 1] = np.radians(float(yaw))
            if pitch is not None:
                self._current_pitch_command[2 * turb_idx] = 1.0
                self._current_pitch_command[2 * turb_idx + 1] = np.radians(float(pitch))
            if torque is not None:
                self._current_torque_command[2 * turb_idx] = 1.0
                self._current_torque_command[2 * turb_idx + 1] = float(torque)
            if ipc is not None:
                ipc_arr = np.radians(np.asarray(ipc, dtype=np.double))
                assert ipc_arr.shape == (3,), "ipc must have 3 elements (one per blade)"
                self._current_ipc_command[4 * turb_idx] = 1.0
                self._current_ipc_command[4 * turb_idx + 1 : 4 * turb_idx + 4] = ipc_arr
        else:
            if yaw is not None:
                self._current_yaw_command[turb_idx + 1] = np.radians(float(yaw))
                self._current_yaw_command[0] = 1.0
            if pitch is not None:
                self._current_pitch_command[turb_idx + 1] = np.radians(float(pitch))
                self._current_pitch_command[0] = 1.0
            if torque is not None:
                self._current_torque_command[turb_idx + 1] = float(torque)
                self._current_torque_command[0] = 1.0
            if ipc is not None:
                ipc_arr = np.radians(np.asarray(ipc, dtype=np.double))
                assert ipc_arr.shape == (3,), "ipc must have 3 elements (one per blade)"
                self._current_ipc_command[turb_idx * 3 + 1 : turb_idx * 3 + 4] = ipc_arr
                self._current_ipc_command[0] = 1.0

    def step(self):
        """Send buffered commands via MPI and advance the simulation by one timestep.

        Returns:
            bool: True if max iterations reached.
        """
        assert self.current_measures is not None, "Call `init` before `step`"

        self._comm.Send(
            buf=self._current_yaw_command,
            dest=self._target_process_rank,
            tag=self.YAW_TAG,
        )
        self._comm.Send(
            buf=self._current_pitch_command,
            dest=self._target_process_rank,
            tag=self.PITCH_TAG,
        )
        self._comm.Send(
            buf=self._current_torque_command,
            dest=self._target_process_rank,
            tag=self.TORQUE_TAG,
        )
        self._comm.Send(
            buf=self._current_ipc_command,
            dest=self._target_process_rank,
            tag=self.IPC_TAG,
        )
        power, wind = self._wait_for_sim_output()
        self._power_buffers.add(power)
        self._wind_buffers.add(wind)

        self._num_iter += 1
        if self._num_iter == self.max_iter:
            self._finalize_mpi_comm()

        if self._logging:
            with open(self._log_file, "a") as fp:
                fp.write(
                    f"Sent command YAW {self.get_yaw_command()} - "
                    f" PITCH {self.get_pitch_command()}"
                    f" TORQUE {self.get_torque_command()}\n"
                    f"***********Received Power: {power} - "
                    f"Filtered Power: (window {self._default_avg_window}):"
                    f"{self.avg_powers()} - "
                    f" Wind : {self.avg_wind()}\n"
                )

        return self._num_iter == self.max_iter

    def update_command(
        self,
        yaw: np.ndarray = None,
        pitch: np.ndarray = None,
        torque: np.ndarray = None,
        ipc: np.ndarray = None,
    ):
        """Set commands for all turbines and advance the simulation by one timestep.

        This is a convenience method equivalent to setting all turbine commands
        then calling step(). Fully backward-compatible with the original API.

        Args:
            yaw: Yaw angles in degrees, shape (num_turbines,).
            pitch: Collective pitch angles in degrees, shape (num_turbines,).
            torque: Generator torques in N-m, shape (num_turbines,).
            ipc: Individual pitch control offsets in degrees,
                 shape (num_turbines, 3). Superimposed on top of CPC.

        Returns:
            bool: True if max iterations reached.
        """
        assert self.current_measures is not None, "Call `init` before `update_command`"
        if self._per_turbine_flags:
            if yaw is not None:
                self._current_yaw_command[0::2] = 1.0
                self._current_yaw_command[1::2] = np.radians(yaw.astype(np.double))
            if pitch is not None:
                self._current_pitch_command[0::2] = 1.0
                self._current_pitch_command[1::2] = np.radians(pitch.astype(np.double))
            if torque is not None:
                self._current_torque_command[0::2] = 1.0
                self._current_torque_command[1::2] = torque.astype(np.double)
            if ipc is not None:
                ipc_arr = np.radians(ipc.astype(np.double))  # shape (num_turbines, 3)
                buf = np.zeros(4 * self.num_turbines)
                buf[0::4] = 1.0
                buf[1::4] = ipc_arr[:, 0]
                buf[2::4] = ipc_arr[:, 1]
                buf[3::4] = ipc_arr[:, 2]
                self._current_ipc_command[:] = buf
        else:
            if yaw is not None:
                self._current_yaw_command[1:] = np.radians(yaw.astype(np.double))
                self._current_yaw_command[0] = 1.0
            if pitch is not None:
                self._current_pitch_command[1:] = np.radians(pitch.astype(np.double))
                self._current_pitch_command[0] = 1.0
            if torque is not None:
                self._current_torque_command[1:] = torque.astype(np.double)
                self._current_torque_command[0] = 1.0
            if ipc is not None:
                ipc_arr = np.radians(ipc.astype(np.double))  # shape (num_turbines, 3)
                self._current_ipc_command[1:] = ipc_arr.flatten()
                self._current_ipc_command[0] = 1.0

        return self.step()

    def set_comm(self, comm):
        self._comm = comm

    def init(self):
        self._num_iter = 0
        if self._per_turbine_flags:
            self._current_yaw_command = np.zeros(2 * self.num_turbines, dtype=np.double)
            self._current_pitch_command = np.zeros(2 * self.num_turbines, dtype=np.double)
            self._current_torque_command = np.zeros(2 * self.num_turbines, dtype=np.double)
            self._current_ipc_command = np.zeros(4 * self.num_turbines, dtype=np.double)
        else:
            self._current_yaw_command = np.zeros(self.num_turbines + 1, dtype=np.double)
            self._current_pitch_command = np.zeros(self.num_turbines + 1, dtype=np.double)
            self._current_torque_command = np.zeros(self.num_turbines + 1, dtype=np.double)
            self._current_ipc_command = np.zeros(3 * self.num_turbines + 1, dtype=np.double)
        self._power_buffers.empty()
        self._wind_buffers.empty()

        num_measures = np.array([0], dtype=int)
        self._comm.Recv(
            num_measures, source=self._target_process_rank, tag=self.COM_TAG
        )
        self._comm.Send(
            buf=np.array([self.max_iter], dtype=np.double),
            dest=self._target_process_rank,
            tag=self.COM_TAG,
        )
        self._num_measures = num_measures[0]
        print(
            f"Interface: will receive {self._num_measures} measures at every iteration"
        )
        self.current_measures = (
            np.zeros((self.num_turbines, self._num_measures)) * np.nan
        )

    def _finalize_mpi_comm(self):
        # Disconnect from intercommunicator
        if isinstance(self._comm, MPI.Intercomm):
            self._comm.Disconnect()

    def get_yaw_command(self, turb_idx: int = None):
        if self._per_turbine_flags:
            flags = self._current_yaw_command[0::2]
            all_yaw = np.degrees(self._current_yaw_command[1::2]).copy()
            if turb_idx is not None:
                return all_yaw[turb_idx] if flags[turb_idx] else None
            return all_yaw
        if 1 - self._current_yaw_command[0]:
            return None
        all_yaw = np.degrees(self._current_yaw_command).copy()[1:]
        if turb_idx is not None:
            return all_yaw[turb_idx]
        return all_yaw

    def get_pitch_command(self, turb_idx: int = None):
        if self._per_turbine_flags:
            flags = self._current_pitch_command[0::2]
            all_pitch = np.degrees(self._current_pitch_command[1::2]).copy()
            if turb_idx is not None:
                return all_pitch[turb_idx] if flags[turb_idx] else None
            return all_pitch
        if 1 - self._current_pitch_command[0]:
            return None
        all_pitch = np.degrees(self._current_pitch_command).copy()[1:]
        if turb_idx is not None:
            return all_pitch[turb_idx]
        return all_pitch

    def get_torque_command(self, turb_idx: int = None):
        if self._per_turbine_flags:
            flags = self._current_torque_command[0::2]
            all_torque = self._current_torque_command[1::2].copy()
            if turb_idx is not None:
                return all_torque[turb_idx] if flags[turb_idx] else None
            return all_torque
        if 1 - self._current_torque_command[0]:
            return None
        all_torque = self._current_torque_command.copy()[1:]
        if turb_idx is not None:
            return all_torque[turb_idx]
        return all_torque

    def avg_farm_power(self, window: int = None):
        powers = self.avg_powers(window).squeeze()
        return powers.sum()

    def avg_powers(self, window: int = None, turb_idx: int = None) -> List:
        if window is None:
            window = self._default_avg_window
        powers = np.atleast_1d(self._power_buffers.get_agg(window).squeeze())
        if turb_idx is not None:
            return powers[turb_idx]
        return powers

    def avg_wind(self, window: int = None) -> List:
        if window is None:
            window = self._default_avg_window
        return self._wind_buffers.get_agg(window).squeeze()

    def last_powers(self, window: int = 0, turb_idx: int = None) -> np.ndarray:
        powers = np.atleast_1d(self._power_buffers.get_all(window).squeeze())
        if turb_idx is not None:
            return powers[..., turb_idx]
        return powers

    def last_wind(self, window: int = 0) -> np.ndarray:
        return self._wind_buffers.get_all(window).squeeze()

    def get_measure(self, measure: str, turb_idx: int = None) -> np.ndarray:
        if measure == "freewind_measurements":
            return np.atleast_1d(self.last_wind().squeeze())
        if turb_idx is not None:
            assert 0 <= turb_idx < self.num_turbines, (
                f"turb_idx={turb_idx} out of range [0, {self.num_turbines})"
            )
            return np.atleast_1d(
                self.current_measures[turb_idx, self.measure_map[measure]].squeeze()
            )
        return np.atleast_1d(
            self.current_measures[:, self.measure_map[measure]].squeeze()
        )

    def get_all_measures(self) -> Dict:
        df = pd.DataFrame(self.current_measures, columns=self.measure_names)
        # convert angles to degrees
        df[["yaw", "pitch"]] = np.degrees(df[["yaw", "pitch"]])
        return df

    def _wait_for_sim_output(self):
        size_buffer = self.num_turbines * self._num_measures
        measures = np.zeros(size_buffer, dtype=np.double)
        self._comm.Recv(
            measures, source=self._target_process_rank, tag=self.MEASURES_TAG
        )
        self._comm.Barrier()
        measures = measures.reshape((self.num_turbines, self._num_measures))
        # print(f"Received measures matrix from simulator: {measures}")

        # format wind directions - keep wind direction positive
        directions = measures[:, self.measure_map["wind_direction"]].flatten()
        directions = np.degrees(directions) - 90
        directions[directions < 0] = directions[directions < 0] + 360
        measures[:, self.measure_map["wind_direction"]] = directions

        # retrieve wind speeds and power outputs
        speeds = measures[:, self.measure_map["wind_speed"]].flatten()
        powers = measures[:, self.measure_map["power"]].flatten()

        # get upstream point = point of maximum speed
        upstream_point = np.argmax(speeds)
        wspeed = speeds[upstream_point]
        wdir = directions[upstream_point]
        # wdir = np.degrees(directions[upstream_point])
        # wdir = wdir - 90
        # Keep wind direction positive
        # if wdir < 0:
        #     wdir = wdir + 360
        self.current_measures = measures
        return powers.astype(np.float32), np.array([wspeed, wdir], dtype=np.float32)


class FastFarmInterface(MPI_Interface):
    system_type = platform.system().lower()
    _package_dir = Path(__file__).resolve().parent
    if system_type == "windows":
        # Change this might cause version issue. Keep an eye on the update of FAST.Farm and update the path accordingly.
        # default_exe_path = str(_package_dir / "simulator" / "fastfarm" / "bin" / "FAST.Farm_x64_OMP_2023.exe")
        default_exe_path = str(_package_dir / "simulator" / "fastfarm" / "bin" / "FAST.Farm_x64_OMP_v355.exe")
    else:
        default_exe_path = "FAST.Farm"
    # `wind_measurements` is not read from the simulator
    # but computed by the interface
    measure_map = {
        "wind_speed": 0,
        "power": 1,
        "wind_direction": 2,
        "yaw": 3,
        "pitch": 4,
        "torque": 5,
        "load": [6, 7, 8, 9, 10, 11],
        "platform_tdx": 12,
        "platform_tdy": 13,
        "pitch_blade2": 14,
        "pitch_blade3": 15,
        "freewind_measurements": None,
    }
    # Extended measure map for SC_DLL_Full variant (NumCtrl2SC=69).
    # Adds shaft loads, hub/yaw-bearing moments, nacelle IMU, platform
    # velocities & accelerations, and controller parameter readbacks.
    measure_map_full = {
        # --- Shared with More variant (indices 0-26) ---
        "rotor_speed":           0,   # rad/s
        "generator_speed":       1,   # rad/s
        "power":                 2,   # W
        "wind_speed":            3,   # m/s
        "yaw":                   4,   # rad
        "pitch":                 5,   # rad  (blade 1)
        "pitch_blade2":          6,   # rad
        "pitch_blade3":          7,   # rad
        "load":                  [8, 9, 10, 11, 12, 13],  # OOP(B1-B3), IP(B1-B3) N-m
        "tower_fa_accel":        14,  # m/s²
        "tower_ss_accel":        15,  # m/s²
        "time":                  16,  # s
        "azimuth":               17,  # rad
        "torque":                18,  # N-m
        "wind_speed_hub":        19,  # m/s
        "wind_direction":        20,  # rad
        "platform_tdx":          21,  # m
        "platform_tdy":          22,  # m
        "platform_tdz":          23,  # m
        "platform_rdx":          24,  # rad  (DISCON to_SC[25]=avrSWAP(1004), rad)
        "platform_rdy":          25,  # rad  (DISCON to_SC[26]=avrSWAP(1005), rad)
        "platform_rdz":          26,  # rad  (DISCON to_SC[27]=avrSWAP(1006), rad)
        # --- New in Full variant (indices 27-68) ---
        "shaft_power":           27,  # W        avrSWAP(14)
        "hub_my_rotating":       28,  # N-m      LSSTipMya  avrSWAP(73)
        "hub_mz_rotating":       29,  # N-m      LSSTipMza  avrSWAP(74)
        "hub_my_fixed":          30,  # N-m      LSSTipMys  avrSWAP(75)
        "hub_mz_fixed":          31,  # N-m      LSSTipMzs  avrSWAP(76)
        "yaw_bearing_my":        32,  # N-m      YawBrMyn   avrSWAP(77)
        "yaw_bearing_mz":        33,  # N-m      YawBrMzn   avrSWAP(78)
        "nacelle_roll_accel":    34,  # rad/s²   NcIMURAxs  avrSWAP(82)
        "nacelle_nodding_accel": 35,  # rad/s²   NcIMURAys  avrSWAP(83)
        "nacelle_yaw_accel":     36,  # rad/s²   NcIMURAzs  avrSWAP(84)
        "air_density":           37,  # kg/m³    AirDens    avrSWAP(95)
        "rotor_avg_wind_speed":  38,  # m/s      avrSWAP(96)
        "shaft_torque":          39,  # N-m      LSSTipMxa  avrSWAP(109)
        "shaft_thrust":          40,  # N        LSShftFxa  avrSWAP(110)
        "shaft_force_y":         41,  # N        LSShftFys  avrSWAP(111)
        "shaft_force_z":         42,  # N        LSShftFzs  avrSWAP(112)
        "platform_tvx":          43,  # m/s      avrSWAP(1007)
        "platform_tvy":          44,  # m/s      avrSWAP(1008)
        "platform_tvz":          45,  # m/s      avrSWAP(1009)
        "platform_rvx":          46,  # rad/s    avrSWAP(1010)
        "platform_rvy":          47,  # rad/s    avrSWAP(1011)
        "platform_rvz":          48,  # rad/s    avrSWAP(1012)
        "platform_tax":          49,  # m/s²     avrSWAP(1013)
        "platform_tay":          50,  # m/s²     avrSWAP(1014)
        "platform_taz":          51,  # m/s²     avrSWAP(1015)
        "platform_rax":          52,  # rad/s²   avrSWAP(1016)
        "platform_ray":          53,  # rad/s²   avrSWAP(1017)
        "platform_raz":          54,  # rad/s²   avrSWAP(1018)
        "dll_dt":                55,  # s        avrSWAP(3)
        "pitch_min":             56,  # rad      avrSWAP(6)
        "pitch_max":             57,  # rad      avrSWAP(7)
        "pitch_rate_min":        58,  # rad/s    avrSWAP(8)
        "pitch_rate_max":        59,  # rad/s    avrSWAP(9)
        "demanded_power":        60,  # W        avrSWAP(13)
        "optimal_mode_gain":     61,  # Nm/(rad/s)²  avrSWAP(16)
        "min_gen_speed_opt":     62,  # rad/s    avrSWAP(17)
        "max_gen_speed_opt":     63,  # rad/s    avrSWAP(18)
        "demanded_gen_speed":    64,  # rad/s    avrSWAP(19)
        "demanded_gen_torque":   65,  # N-m      avrSWAP(22)
        "pitch_control_mode":    66,  # flag     avrSWAP(28)
        "yaw_control_mode":      67,  # flag     avrSWAP(29)
        "num_blades":            68,  # count    avrSWAP(61)
        "freewind_measurements": None,
    }
    _MEASURE_MAPS = {
        69: measure_map_full,
    }

    def __init__(
        self,
        num_turbines: int,
        fstf_file: bool,
        buffer_size: int = 50_000,
        log_file: str = None,
        max_iter: int = int(1e4),
        fast_farm_executable: str = default_exe_path,
        default_avg_window: int = 1,
        dt: float = None,
        per_turbine_flags: bool = False,
    ):
        self._path_to_fastfarm_exe = fast_farm_executable
        self._simul_file = fstf_file
        self._inflow_file = get_inflow_file_path(fstf_file)
        self._num_resets = 0
        self.dt = dt

        super().__init__(
            default_avg_window=default_avg_window,
            buffer_size=buffer_size,
            num_turbines=num_turbines,
            log_file=log_file,
            measure_map=self.measure_map,
            comm=None,
            target_process_rank=0,
            max_iter=max_iter,
            per_turbine_flags=per_turbine_flags,
        )

    @classmethod
    # If you already have a Fast.Farm .fstf file defined, you can directly use that by calling this
    def from_file(
        cls,
        fstf_file,
        fast_farm_executable: str = default_exe_path,
        buffer_size: int = 50_000,
        log_file: str = None,
        default_avg_window: int = 1,
        per_turbine_flags: bool = False,
    ):
        print(f"Simulation will be started from fstf file {fstf_file}")
        num_turbines, max_iter, dt = read_simul_info(fstf_file)
        try:
            print(f"Copying DLLs for simulation {fstf_file}")
            create_dll(fstf_file)
        except KeyError as e:
            warnings.warn(
                f"Could not auto-copy DLLs ({e}). "
                "Assuming SC_DLL.dll and DISCON DLLs are already in place "
                "relative to the .fstf file."
            )

        return cls(
            num_turbines=num_turbines,
            fstf_file=fstf_file,
            default_avg_window=default_avg_window,
            buffer_size=buffer_size,
            log_file=log_file,
            max_iter=max_iter,
            fast_farm_executable=fast_farm_executable,
            dt=dt,
            per_turbine_flags=per_turbine_flags,
        )

    def init(self, wind_speed: float = None, wind_direction: float = None):
        # wind speed and direction ignored for now
        if wind_direction is not None:
            warnings.warn(
                f"Wind direction = {wind_direction} requested, but FastFarmInterface"
                "cannot set wind direction in the simulator. Request will be ignored."
            )

        if wind_speed is not None:
            simul_wind_speed = read_inflow_info(self._inflow_file)
            if simul_wind_speed != wind_speed:
                write_inflow_info(self._inflow_file, float(wind_speed))

        simul_file = reset_simul_file(self._simul_file, self._num_resets)
        print("Spawning process", self._path_to_fastfarm_exe, simul_file)
        spawn_comm = MPI.COMM_SELF.Spawn(
            self._path_to_fastfarm_exe, args=[simul_file], maxprocs=1
        )
        self.set_comm(spawn_comm)
        self._num_resets += 1
        super().init()
        # Auto-select measure map based on num_measures received from SC_DLL handshake
        if self._num_measures in self._MEASURE_MAPS:
            self._validate_measure_map(self._MEASURE_MAPS[self._num_measures])
