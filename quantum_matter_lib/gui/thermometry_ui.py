import json
from pathlib import Path
import sys
import time

try:
    from PyQt6.QtCore import (
        QObject,
        QSize,
        QThread,
        Qt,
        pyqtSignal,
        pyqtSlot
    )
    from PyQt6.QtGui import QCursor, QDoubleValidator
    from PyQt6.QtWidgets import (
        QApplication,
        QComboBox,
        QDialog,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLCDNumber,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
        QWidget
    )
except ImportError:
    raise ImportError("PyQt6 is required for gui applications.")

import pyvisa
from pymeasure.instruments.srs.sr830 import SR830

import numpy as np

CONFIG_FILE = "config.json"
CONFIG_DEFAULT = {
    "bias_resistance": 1e6,
    "lockin_voltage": 4e-3,
    "R0": 2150.0,
    "a0": 0,
    "a1": 0,
    "a2": 0,
    "a3": 0,
    "a4": 0,
    "a5": 0,
}

class WorkerTempReading(QObject):
    update = pyqtSignal(float)

    def get_T(self) -> float:
        v = self.lockin.x
        i = self.lockin.sine_voltage/self.config["bias_resistance"]
        r = v/i
        l_r = np.log(r - self.config["R0"])
        sum = 0
        for i in range(6):
            sum += self.config[f"a{i}"]*l_r**i
        return 1/np.exp(sum)

    def __init__(self, lockin: SR830, config: dict) -> None:
        super().__init__()
        self.lockin = lockin
        self.config = config
    
    @pyqtSlot()
    def run(self):
        self.running = True
        while self.running:
            self.update.emit(self.get_T())
            time.sleep(3)

    @pyqtSlot()
    def stop(self):
        self.running = False

    @pyqtSlot()
    def update_config(self, config: dict):
        self.config = config

class MainWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()

        self.rm = pyvisa.ResourceManager()
        self.lockin: SR830 | None = None
        self.status = 0
        self.edit_window: EditWindow | None = None

        # Check if config file exist and load
        if not Path(CONFIG_FILE).is_file():
            with open(CONFIG_FILE, 'w') as f:
                json.dump(CONFIG_DEFAULT, f)
        with open(CONFIG_FILE, 'r') as f:
            self.config = json.load(f)

        # Threads
        self.thread_temp = QThread()
        self.worker_temp: WorkerTempReading | None = None

        self.setWindowTitle("Lockin temperature measurement UI")
        self.setFixedSize(QSize(400, 150))

        widget = QWidget()
        layout = QGridLayout()
        widget_b = QWidget()
        layout_b = QVBoxLayout()

        self.connect = QPushButton("Connect")
        self.edit = QPushButton("Edit")
        self.temp = QLCDNumber()
        self.temp_l = QLabel("K")
        self.gpib = QComboBox()
        self.gpib_l = QLabel("GPIB address:")
        self.gpib_refresh = QPushButton("Refresh")
        self.status_bar = self.statusBar()

        layout.addWidget(self.gpib_l, 0, 0)
        layout.addWidget(self.gpib, 0, 1, 1, 2)
        layout.addWidget(self.gpib_refresh, 0, 3)
        layout.addWidget(widget_b, 1, 0)
        layout.addWidget(self.temp, 1, 1, 3, 2)
        layout.addWidget(self.temp_l, 1, 3, 3, 1)

        layout_b.addWidget(self.connect)
        layout_b.addWidget(self.edit)

        # Populate widgets
        self.gpib.addItems(self.rm.list_resources())
        self.gpib.addItems(["Test 1", "Test 2"])  # To remove

        # Signal
        self.gpib_refresh.clicked.connect(self.refresh_gpib_list)
        self.connect.clicked.connect(self.connect_slot)
        self.edit.clicked.connect(self.edit_slot)

        widget.setLayout(layout)
        widget_b.setLayout(layout_b)
        self.setCentralWidget(widget)

    def refresh_gpib_list(self) -> None:
        self.status_bar.showMessage("Looking for GPIB devices...")
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        self.gpib.clear()
        self.gpib.addItems(self.rm.list_resources())
        self.status_bar.showMessage(f"Found {self.gpib.count()} GPIB devices.", 5000)
        QApplication.restoreOverrideCursor()

    def connect_slot(self)-> None:
        if self.status == 0:
            try:
                self.lockin = SR830(self.gpib.currentText())
                self.lockin.x
            except Exception as e:
                self.status_bar.showMessage(f"Disconnected.")
                self.lockin = None
                m = QMessageBox(self)
                m.setWindowTitle("Error")
                m.setText(f"Could not connect to {self.gpib.currentText()}.\n{e}")
                m.setStandardButtons(QMessageBox.StandardButton.Yes)
                m.setIcon(QMessageBox.Icon.Critical)
                m.show()
                return
            
            self.status_bar.showMessage(f"Connected to {self.gpib.currentText()}.")
            self.connect.setText("Disconnect")
            self.status = 1

            # Start thread
            self.worker_temp = WorkerTempReading(self.lockin, self.config)
            self.worker_temp.moveToThread(self.thread_temp)
            self.thread_temp.started.connect(self.worker_temp.run)
            self.worker_temp.update.connect(self.update_LCD)
            self.thread_temp.start()
        elif self.status == 1:
            if self.worker_temp:
                self.worker_temp.stop()
            self.status_bar.showMessage(f"Disconnected.")
            self.connect.setText("Connect")
            self.status = 0

    def edit_slot(self):
        if self.edit_window == None:
            self.edit_window = EditWindow()
        self.edit_window.send_config.connect(self.update_config)
        if self.worker_temp:
            self.edit_window.send_config.connect(self.worker_temp.update_config)
        self.edit_window.show()

    @pyqtSlot(dict)
    def update_config(self, config: dict):
        self.config = config

    @pyqtSlot(float)
    def update_LCD(self, value: float):
        if value >= 1:
            # Kelvin range
            self.temp.display(value)
            self.temp_l.setText("K")
        else:
            # mK range
            self.temp.display(value*1e3)
            self.temp_l.setText("mK")


class EditWindow(QDialog):
    send_config = pyqtSignal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Parameters")
        self.resize(600, 400)

        layout = QVBoxLayout()
        layout_resistance= QHBoxLayout()
        layout_voltage= QHBoxLayout()
        layout_r0 = QHBoxLayout()

        self.resistance = QLineEdit()
        self.resistance.setValidator(QDoubleValidator())
        self.resistance_l = QLabel("Bias resistance (Ohm)")
        self.resistance_w = QWidget()
        self.voltage = QLineEdit()
        self.voltage.setValidator(QDoubleValidator())
        self.voltage_l = QLabel("Lockin output voltage (V)")
        self.voltage_w = QWidget()
        self.r0 = QLineEdit()
        self.r0.setValidator(QDoubleValidator())
        self.r0_l = QLabel("R0 (Ohm)")
        self.r0_w = QWidget()
        self.exp = QLabel("log(1/T)=sum(i=0->5)[a_i*log(r_i - r0)^i]")
        self.coeff: list[QLineEdit] = []
        self.coeff_l: list[QLabel] = []
        for i in range(6):
            le = QLineEdit()
            le.setValidator(QDoubleValidator())
            self.coeff.append(le)
            self.coeff_l.append(QLabel(f"A{i}"))
        self.save = QPushButton("Save")

        self.resistance_w.setLayout(layout_resistance)
        layout_resistance.addWidget(self.resistance_l)
        layout_resistance.addWidget(self.resistance)

        self.voltage_w.setLayout(layout_voltage)
        layout_voltage.addWidget(self.voltage_l)
        layout_voltage.addWidget(self.voltage)

        self.r0_w.setLayout(layout_r0)
        layout_r0.addWidget(self.r0_l)
        layout_r0.addWidget(self.r0)

        layout.addWidget(self.resistance_w)
        layout.addWidget(self.voltage_w)
        layout.addWidget(self.r0_w)
        layout.addWidget(self.exp)

        for i in range(6):
            widget = QWidget()
            layout_coeff = QHBoxLayout()
            layout_coeff.addWidget(self.coeff_l[i])
            layout_coeff.addWidget(self.coeff[i])
            widget.setLayout(layout_coeff)
            layout.addWidget(widget)

        layout.addWidget(self.save)
        
        self.setLayout(layout)

        # Load parameters
        with open(CONFIG_FILE, "r") as f:
            self.config = json.load(f)
        self.resistance.setText(str(self.config["bias_resistance"]))
        self.r0.setText(str(self.config["R0"]))
        self.voltage.setText(str(self.config["lockin_voltage"]))
        for i in range(6):
            self.coeff[i].setText(str(self.config[f"a{i}"]))

        # Connect slots
        self.save.clicked.connect(self.save_slot)

    def save_slot(self):
        config = {
            "bias_resistance": float(self.resistance.text()),
            "lockin_voltage": float(self.voltage.text()),
            "a0": float(self.coeff[0].text()),
            "a1": float(self.coeff[1].text()),
            "a2": float(self.coeff[2].text()),
            "a3": float(self.coeff[3].text()),
            "a4": float(self.coeff[4].text()),
            "a5": float(self.coeff[5].text()),
            "R0": float(self.r0.text())
        }

        # Save and emit signal
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        self.send_config.emit(config)

        self.close()
        

def run() -> int:
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    return app.exec()