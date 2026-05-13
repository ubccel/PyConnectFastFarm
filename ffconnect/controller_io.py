from dataclasses import dataclass, make_dataclass, field
from typing import Type

@dataclass
class ControlInput:
    pass

@dataclass
class StateMeasurement:
    pass

def construct_control_input(input_list) -> Type[ControlInput]:
    inputs = [(i, float, field(default=None)) for i in input_list]
    return make_dataclass('ControlInput', inputs)

def construct_state_measurment(states_list) -> Type[StateMeasurement]:
    states = [(s, float, field(default=None)) for s in states_list]
    return make_dataclass('StateMeasurement', states)


ControlInput = construct_control_input(
    ['generator_torque', 'blade_pitch', 'nacelle_yaw']
)

StateMeasurement = construct_state_measurment(
    ['wind_speed', 'wind_direction', 'position']
)