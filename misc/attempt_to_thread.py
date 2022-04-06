from PyQt5 import QtWidgets, QtCore, uic
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from pyqtgraph import PlotWidget, plot
import pyqtgraph as pg
import sys
import numpy as np
import serial.tools.list_ports
import os
import time
from dkc_rehamovelib.DKC_rehamovelib import *  # Import our library
from datetime import datetime
import itertools

ADC_ENABLED = False

if ADC_ENABLED:
    import busio
    import board
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn

SAMPLES = 1000
SAMPLES_ = 100
DATA_NB = 1
global TEMP_STORAGE
TEMP_STORAGE = []

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
# MAIN WINDOW:
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# https://www.youtube.com/watch?v=XXPNpdaK9WA


class Window2(QtWidgets.QMainWindow):
    def __init__(self, myFES, myADC, *args, **kwargs):
        super(Window2, self).__init__(*args, **kwargs)
        uic.loadUi('resources/_CD_GUI_Main_Formed.ui',
                   self)  # load ui from Qt Designer

        #### Setup GUI Widgets ####
        # Setup FES Channels and Parameters
        self.channel_cb.addItems(
            [' ', '1 (Red)', '2 (Blue)', '3 (Black)', '4 (White)'])
        self.amp_sp.setRange(0, 50)  # FES amplitude (mA)
        self.amp_sp.setValue(15)
        self.dur_sp.setRange(0, 500)  # FES duration (us)
        self.dur_sp.setValue(150)
        self.f_sp.setRange(0, 10)  # FES frequency (Hz)
        self.f_sp.setValue(1)
        self.np_sp.setRange(0, 100)  # FES number of pulses (int)
        self.np_sp.setValue(1)

        # Connect push and check buttons
        # commit parameters to FES system
        self.commit_pb.clicked.connect(self.update_lcd)
        self.target_cb.toggled.connect(
            self.update_target)  # add target line to plot
        self.download_pb.clicked.connect(self.download)  # download data
        self.sendPulse_pb.clicked.connect(
            self.try_fes)  # send a single FES burst
        self.CD_pb.clicked.connect(self.connect_to_Window3)  # go to CD window

        # Set start time
        self.time_start = time.time()
        self.max_value_reached = 0
        self.data_to_save = []

        #### Setup PYQTGRAPH ####
        # Preassign data
        self.x = [0] * SAMPLES
        self.y1 = [0] * SAMPLES
        self.x_storage = []
        self.y1_storage = []

        # Create a plot window
        self.graphWidget = pg.PlotWidget()
        self.findChild(QWidget, "TorquePlot").layout(
        ).addWidget(self.graphWidget)
        self.graphWidget.setBackground('w')
        self.graphWidget.setTitle("Central Drive Estimation")
        self.graphWidget.setLabel('left', 'Torque (ft-lbs)')
        self.graphWidget.setLabel('bottom', 'Samples')
        self.graphWidget.showGrid(x=False, y=True)
        # self.graphWidget.setYRange(0, 10, padding=1)
        self.graphWidget.enableAutoRange('y', 0.95)
        self.graphWidget.addLegend()

        # Prepare scrolling line
        pen_ref = pg.mkPen(color=(192, 192, 192), width=1,
                           style=QtCore.Qt.DashLine)
        pen1 = pg.mkPen(color=(0, 123, 184), width=2)
        self.data_line1 = self.graphWidget.plot(
            self.x, self.y1, pen=pen1, name="Torque Sensor")

        #### Setup Timer ####
        self.timer = QtCore.QTimer()
        self.timer.setInterval(1)
        self.timer.timeout.connect(self.update_gui)
        self.timer.start()

        #### Miscellaneous ####
        # Setup a PAUSE button in a toolbar
        self.toolbar = self.addToolBar("Pause")
        self.pause_tb = QAction("Pause", self)
        self.pause_tb.triggered.connect(self.pause_plotting)
        self.pause_tb.setCheckable(True)
        self.toolbar.addAction(self.pause_tb)

        # Thread
        # self.worker = WorkerThread()
        # self.worker.start()
        # self.worker.update_signal.connect(self.signal_emitted_thread)

        thread = DataLoggingThread(parent = self)
        thread.newData.connect(self.thread_update)
        thread.start()

    #### GUI AND PLOTTING METHODS ####
    def thread_update(self, data):
        self.data_to_save.append(float(data - self.time_start))
        
    def update_gui(self):
        """Master method called by timer to update plot."""
        self.update_plot()

    def update_lcd(self):
        """Update the FES parameters to reflect commited values."""
        self.committedAmp_lbl.display(self.amp_sp.value())
        self.committedDur_lbl.display(self.dur_sp.value())
        self.committedF_lbl.display(self.f_sp.value())
        self.committedNp_lbl.display(self.np_sp.value())

    def update_target(self):
        """Add target line in red to plot for participant to try and reach."""
        if self.target_cb.isChecked():
            self.target = pg.InfiniteLine(movable=True, angle=0, pen={'color': 'r', 'width': 10}, label='Torque Target ={value:0.2f}',
                                          labelOpts={'position': 0.5, 'color': (200, 0, 0), 'fill': (200, 200, 200, 50), 'movable': True})
            self.graphWidget.addItem(self.target)
        else:
            self.graphWidget.removeItem(self.target)

    def update_plot(self):
        self.x = self.add_data(self.x, time.time()-self.time_start)
        self.x_storage.append(float(time.time()-self.time_start))

        if ADC_ENABLED:
            self.y1 = self.add_data(self.y1, (myADC.voltage))
            self.y1_storage.append(float(myADC.voltage))
        else:
            self.y1 = self.add_data(self.y1, np.random.randint(0, 10))
            self.y1_storage.append(np.random.randint(0, 10))

        self.graphWidget.setXRange(self.x[-100], self.x[-1], padding=1)
        self.data_line1.setData(self.x, self.y1)

        # Add max value reached to plot
        # if ADC_ENABLED:
        # 	if (float(myADC.voltage) > self.max_value_reached):
        # 		self.max_value_reached = (float(myADC.voltage))
        # 		self.committedNp_lbl.display(self.max_value_reached)

    def add_data(self, data_buffer, new_data):
        """Store new data in buffer."""
        data_buffer = data_buffer[1:]
        data_buffer.append(float(new_data))
        return data_buffer

    #### FES METHODS ####
    def try_fes(self):
        """If FES is enabled, update values and send a pulse."""
        if self.fesEnable_cb.isChecked():
            self.update_and_send_pulse_fes()
        else:
            pass

    def update_and_send_pulse_fes(self):
        """Update FES parameters and send pulse."""
        amp = int(self.committedAmp_lbl.value())  # [mA]
        dur = int(self.committedDur_lbl.value())  # [us]
        f = int(self.committedF_lbl.value())  # hz
        n_pulse = int(self.committedNp_lbl.value())
        try:
            # for channels: 1 = red, 2 = blue, 3 = black, 4 = white
            channelNum = int(self.channel_cb.currentText()[0])
            self.send_pulse_fes(amp, dur, f, n_pulse, channelNum)
        except:
            print('No Channel Selected')

    def send_pulse_fes(self, amp, dur, f, n_pulse, channelNum):
        """Send pulse to FES."""
        for i in range(0, n_pulse):
            if f == 1:
                # Send pulse every second
                myFES.write_pulse(
                    channelNum, [(dur, amp), (50, 0), (dur, -amp)])
                print('Hasomed Pulse Sent')
            else:
                # Send pulse every second
                myFES.write_pulse(
                    channelNum, [(dur, amp), (50, 0), (dur, -amp)])
                print('Hasomed Pulse Sent')
                time.sleep(1.0/f)

    #### MISCELLANEOUS METHODS ####
    def connect_to_Window3(self):
        pass

    def signal_emitted_thread(self, list_to_save):
        self.data_to_save.append(list_to_save - self.time_start)
        print('here')

    def download(self):
        self.timer.stop()
        """Download data from GUI."""
        default_filename = 'data/CD_' + datetime.now().strftime("%Y%m%d-%H%M%S")
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save data file", default_filename, "CSV Files (*.csv)")
        if filename:
            # data_to_save = list(zip(self.data_to_save, self.x_storage, self.y1_storage))
            data_to_save = list(itertools.zip_longest(self.data_to_save, self.x_storage, self.y1_storage))
            #create headers for file
            header1 = "FES Amp = " + str(self.committedAmp_lbl.value())
            header2 = "FES Dur = " + str(self.committedDur_lbl.value())
            header3 = "FES F = " + str(self.committedF_lbl.value())
            header4 = "FES Np = " + str(self.committedNp_lbl.value())
            header5 = "Thread Time (s), GUI Time (s), GUI Voltage (V)"
            #save data to file
            np.savetxt(filename, data_to_save, delimiter=',', fmt='%s', comments = '', 
                header = '\n'.join([header1, header2, header3, header4, header5]))
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setText("Download completed successfully!")
            msg.setWindowTitle("Success")
            msg.exec()
        self.timer.start()

    def key_press_event(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            self.close()

    def pause_plotting(self):
        """Pause plotting by stopping background the timer."""
        if self.pause_tb.isChecked():
            self.timer.stop()
        else:
            self.timer.start()


# class WorkerThread(QThread):
#     update_signal = pyqtSignal(float)
#     def run(self):
#         self.update_signal.emit(float(time.time()))

class DataLoggingThread(pg.QtCore.QThread):
    newData = pg.QtCore.Signal(float)
    def run(self):
        while True:
            data = np.random.normal(size=100)
            # do NOT plot data from here!
            self.newData.emit(float(time.time()))
            time.sleep(0.0005)


# SETUP:
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
app = QtWidgets.QApplication(sys.argv)

# setup FES
myFES = Rehamove_DKC("None")

if ADC_ENABLED:
        # setup ADC
    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS.ADS1115(i2c)
    # Create single-ended input on channel 0
    myADC = AnalogIn(ads, ADS.P0)
else:
    myADC = None

w = Window2(myFES, myADC)
w.show()
myFES.close()
sys.exit(app.exec_())
