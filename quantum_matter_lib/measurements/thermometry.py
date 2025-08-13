"""
Module with a set of functions related to the thermometry inside our cryostat
"""
import json

import numpy as np

RESISTANCE_CALIBRATION_FILE = "config/thermometry/resistance_calibration.json"

def temperature_ruo2(resistance: float, name: str) -> float:
    """
    Conversion from resistance  to temperature using polynomial fit.
    It uses the data from `config/thermometry/resistance_calibration.json`.

    The calibration must be a child of `ruo2` and have the following format:

    .. code-block:: json

        {"R0": 2200.0, "a": [1.0, 2.0]}

    with "R0" the resistance at room temperature and a the the coefficients of the polynom.

    The polynomial fit have the following expression:

    .. math::
        \\log(1/T)=\\sum_{i=0}^{len(a)}a_i\\log(R - R_0)^i


    Source: https://www.epfl.ch/labs/lqm/wp-content/uploads/2018/07/TPIV_Pau_LQM.pdf


    :param resistance: Value of the resistance in ohm
    :type resistance: float
    :param name: Name of the resistance in calibration data
    :type name: str
    :raises Exception: Unable to parse calibration data file
    :raises Exception: Calibration for the given resistance name does not exist
    :raises Exception: Invalid calibration
    :return: Temperature in kelvin
    :rtype: float
    """    

    # Load configuration
    with open(RESISTANCE_CALIBRATION_FILE, "r") as f:
        data = json.load(f)['ruo2']
    if data is None:
        raise Exception("Unable to parse data file.")
    if not name in data:
        raise Exception(f"Resistance {name} does not exist in configuration file.")
    r_data = data[name]
    if (not "R0" in r_data) or (not "a" in r_data):
        raise Exception(f"The calibration for this resistance is not valid.")

    # Compute resistance with polynomial fit
    l_r = np.log(resistance - r_data["R0"])
    sum = 0
    for i in range(len(r_data["a"])):
        sum +=  r_data["a"][i]*l_r**i
    return float(1/np.exp(sum))
