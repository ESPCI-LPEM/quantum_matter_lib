import json

import numpy as np

RESISTANCE_CALIBRATION_FILE = "config/thermometry/resistance_calibration.json"

def temperature_ruo2(resistance: float, name: str) -> float:

    # Load configuration
    with open(RESISTANCE_CALIBRATION_FILE, "r") as f:
        data = json.load(f)['ruo2']
    if data is None:
        raise Exception("Unable to parse data file.")
    if not name in data:
        raise Exception(f"Resistance {name} does not exist in configuration file.")
    r_data = data[name]
    if (not "R0" in r_data) or (not "a" in r_data):
        raise Exception(f"The configuration for this resistance is not valid.")

    # Compute resistance with polynomial fit
    l_r = np.log(resistance - r_data["R0"])
    sum = 0
    for i in range(len(r_data["a"])):
        sum +=  r_data["a"][i]*l_r**i
    return float(1/np.exp(sum))
