# IMPORTS
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
#PyQt Imports
from PyQt5 import QtWidgets, QtCore, uic
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
#PyQtGraph Imports
from pyqtgraph import PlotWidget, plot
import pyqtgraph as pg
#Helper Imports
import os
import sys
import time
import numpy as np
import itertools
import serial.tools.list_ports
from datetime import datetime
#FES Imports
from dkc_rehamovelib.DKC_rehamovelib import *  # Import our library


# INITIALIZE VARIABLES
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
ADC_ENABLED = True

if ADC_ENABLED:
    import busio
    import board
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn

SAMPLES = 1000
SAMPLES_ = 100
DATA_NB = 1
THREAD_SPEED = 0
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"


# WINDOW: LANDING PAGE
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
class Window1(QDialog):
    def __init__(self, myFES, myADC, *args, **kwargs):
        super().__init__(*args, **kwargs)
        uic.loadUi('resources/_CD_GUI_Landing_Formed.ui', self)

        # find existing COM Ports
        self.comports = serial.tools.list_ports.comports(include_links=True)
        for comport in self.comports:
            self.portSelect_cb.addItem(comport.description)
        self.startPlotting_pb.clicked.connect(self.connect_to_main)

    def key_press_event(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()

    def connect_to_main(self):
        self.w2 = Window2(myFES, myADC)
        self.w2.comport_le.setText(
            self.comports[self.portSelect_cb.currentIndex()].device)
        # print(str(self.comports[self.portSelect_cb.currentIndex()].device))
        # myFES = Rehamove_DKC(str(self.comports[self.portSelect_cb.currentIndex()].device)); # Open USB port (on Windows) -- maybe will want a dropdown
        # self.w2.FES.write_pulse(2, [(150,  10), (50, 0), (150, -10)])
# 		myFES.port = str(self.comports[self.portSelect_cb.currentIndex()].device)
        myFES.port = "/dev/ttyUSB0"
        myFES.connect()
        myFES.initialize()
        if not myFES.is_connected():
            # self.connect_lbl.setText('Successful')
            # self.connect_lbl.setStyleSheet('color: Green')
            # time.sleep(1)
            self.w2.show()
            self.close()
        else:
            self.connect_lbl.setText('Unsuccessful')
            self.connect_lbl.setStyleSheet('color: red')

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

        #### Initialize Variables ####
        self.time_start = time.time()
        self.max_value_reached = 0
        self.threadX = [0]
        self.threadY = [0]
        self.windowFlag = 0 #0 if Window 2, 1 if Window 3
        self.windowFlagList = [0]
        
        #### Setup PYQTGRAPH ####
        # Preassign data
        self.x = [0] * SAMPLES #list(range(SAMPLES))
        self.y = [0] * SAMPLES
        self.x_storage = [0]
        self.y_storage = [0]
        self.pyqtTimerTime = [0]

        # Create a plot window
        self.graphWidget = pg.PlotWidget()
        self.findChild(QWidget, "TorquePlot").layout(
        ).addWidget(self.graphWidget)
        self.graphWidget.setBackground('w')
        self.graphWidget.setTitle("Central Drive Estimation")
        self.graphWidget.setLabel('left', 'Torque (ft-lbs)')
        self.graphWidget.setLabel('bottom', 'Samples')
        self.graphWidget.showGrid(x=False, y=True)
        #self.graphWidget.setYRange(0, 10, padding=1)
        self.graphWidget.enableAutoRange(axis = 'y')
        self.graphWidget.setAutoVisible(y = True)
        self.graphWidget.addLegend()

        # Prepare scrolling line
        pen_ref = pg.mkPen(color=(192, 192, 192), width=1,
                           style=QtCore.Qt.DashLine)
        pen1 = pg.mkPen(color=(0, 123, 184), width=2)
        self.data_line1 = self.graphWidget.plot(
            self.x, self.y, pen=pen1, name="Torque Sensor")

        #### Setup Timer ####
        self.timer = QtCore.QTimer()
        self.timer.setInterval(0)
        self.timer.timeout.connect(self.update_gui)
        self.timer.start()
        
        #### Data Logging Thread ####
        thread = DataLoggingThread(parent = self)
        thread.newData.connect(self.thread_update)
        thread.start()

        #### Miscellaneous ####
        # Setup a PAUSE button in a toolbar
        self.toolbar = self.addToolBar("Pause")
        self.pause_tb = QAction("Pause", self)
        self.pause_tb.triggered.connect(self.pause_plotting)
        self.pause_tb.setCheckable(True)
        self.toolbar.addAction(self.pause_tb)

    #### GUI AND PLOTTING METHODS ####
    def update_gui(self):
        """Master method called by timer to update plot."""
        self.update_plot()

    def thread_update(self, data):
        """Method called by thread to continuously append data"""
        self.threadX.append(float(data[0] - self.time_start)) #time
        self.threadY.append(float(data[1])) #voltage
        self.windowFlagList.append(self.windowFlag)

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
        """Update the plot with new data."""
        temp_x = self.threadX[-1]
        temp_y = self.threadY[-1]
        
        self.x = self.add_data(self.x, temp_x)
        self.x_storage.append(temp_x)

        self.y = self.add_data(self.y, temp_y)
        self.y_storage.append(temp_y)

        self.pyqtTimerTime.append(time.time() - self.time_start) #stores time of loop access

        self.graphWidget.setXRange(self.x[-100], self.x[-1], padding=1)
        self.data_line1.setData(self.x, self.y)

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
        """Connect to Window3."""
        self.w3 = Window3(self)
        self.windowFlag = 1
        self.close()
        self.w3.show()

    def download(self):
        self.timer.stop()
        """Download data from GUI."""
        default_filename = 'data/CD_' + datetime.now().strftime("%Y%m%d-%H%M%S")
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save data file", default_filename, "CSV Files (*.csv)")
        if filename:
            # data_to_save = list(zip(self.data_to_save, self.x_storage, self.y_storage))
            data_to_save = list(itertools.zip_longest(self.threadX, self.threadY, self.x_storage, self.y_storage, self.pyqtTimerTime, self.windowFlagList))
            #create headers for file
            header1 = "FES Amp = " + str(self.committedAmp_lbl.value())
            header2 = "FES Dur = " + str(self.committedDur_lbl.value())
            header3 = "FES F = " + str(self.committedF_lbl.value())
            header4 = "FES Np = " + str(self.committedNp_lbl.value())
            header5 = "Thread Time (s), Thread Voltage (V), GUI Time (s), GUI Voltage (V), Inner Loop Time (s), 'Window Flag"
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


# CENTRAL DRIVE WINDOW:
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
class Window3(QtWidgets.QMainWindow):
    def __init__(self, w2, *args, **kwargs):
        super(Window3, self).__init__(*args, **kwargs)
        uic.loadUi('resources/_CD_GUI_CDTest_Formed.ui',
                   self)  # load ui from Qt Designer

        #### Initialize Variables ####
        self.w22 = w2
        self.test_complete = False
        self.time_start = time.time()
        self.pyqtTimerTime = [0]

        #### Setup GUI Widgets ####
        # Grab values commited to Hasomed Device from Window2
        self.channel_lbl.setText(self.w22.channel_cb.currentText())
        self.committedAmp_lbl.display(
            self.w22.committedAmp_lbl.value())  # FES amplitude (mA)
        self.committedDur_lbl.display(
            self.w22.committedDur_lbl.value())  # FES Duration (us)
        self.committedF_lbl.display(
            self.w22.committedF_lbl.value())  # FES frequency (Hz)
        # FES number of pulses (int)
        self.committedNp_lbl.display(self.w22.committedNp_lbl.value())

        # Connect push buttons and spinners
        self.target_cb.toggled.connect(self.update_target)
        self.download_pb.clicked.connect(self.download)
        self.returnToMain_pb.clicked.connect(self.connect_to_main)

        #### Setup PYQTGRAPH ####
        # Preassign data
        # self.x = list(range(SAMPLES))
        self.x = [0] * SAMPLES
        self.y = [0] * SAMPLES
        self.x_storage = [0]
        self.y_storage = [0]

        # Create a plot window
        self.graphWidget = pg.PlotWidget()
        self.findChild(QWidget, "TorquePlot").layout().addWidget(self.graphWidget)
        self.graphWidget.setBackground('w')
        self.graphWidget.setTitle("Central Drive Estimation")
        self.graphWidget.setLabel('left', 'Torque (ft-lbs)')
        self.graphWidget.setLabel('bottom', 'Samples')
        self.graphWidget.showGrid(x=False, y=True)
        # self.graphWidget.setYRange(0, 10, padding=1)
        self.graphWidget.enableAutoRange(axis = 'y')
        self.graphWidget.setAutoVisible(y = True)
        self.graphWidget.addLegend()

        # Prepare scrolling line
        pen_ref = pg.mkPen(color=(192, 192, 192), width=1,
                           style=QtCore.Qt.DashLine)
        pen1 = pg.mkPen(color=(0, 123, 184), width=2)
        self.data_line1 = self.graphWidget.plot(
            self.x, self.y, pen=pen1, name="Torque Sensor")

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

    #### GUI AND PLOTTING METHODS ####
    def update_gui(self):
        """Master method called by timer to update plot."""
        self.update_plot()

    def update_lcd(self):
        """Update the FES parameters to reflect commited values."""
        self.amp_lcd.display(self.amp_sp.value())

    def update_target(self):
        """Add target line in red to plot for participant to try and reach."""
        if self.target_cb.isChecked():
            self.target = pg.InfiniteLine(movable=True, angle=0, pen={'color': 'r', 'width': 10}, label='Torque Target ={value:0.2f}',
                                          labelOpts={'position': 0.5, 'color': (200, 0, 0), 'fill': (200, 200, 200, 50), 'movable': True})
            self.graphWidget.addItem(self.target)
        else:
            self.graphWidget.removeItem(self.target)

    def update_plot(self):
        """Update the plot with new data."""
        temp_x = self.w22.threadX[-1]
        temp_y = self.w22.threadY[-1]
        
        self.x = self.add_data(self.x, temp_x)
        self.x_storage.append(temp_x)

        self.y = self.add_data(self.y, temp_y)
        self.y_storage.append(temp_y)

        self.pyqtTimerTime.append(time.time() - self.time_start) #stores time of loop access

        self.graphWidget.setXRange(self.x[-100], self.x[-1], padding=1)
        self.data_line1.setData(self.x, self.y)

        # Detect if steady state reached
        if ADC_ENABLED:
            if not self.test_complete:
                if temp_y > 0:
                    if int(np.size(self.y_storage)) > 51:
                        if not np.any(np.array(self.y_storage[-50:]) < 0):
                            print('success')
                            self.test_complete = True

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
                print('Hasomedd Pulse Sent')
                time.sleep(1.0/f)

    #### MISCELLANEOUS METHODS ####
    def connect_to_main(self):
        """Connect to main GUI."""
        self.w22.windowFlag = 0
        self.w22.show()
        self.close()

    def download(self):
        self.timer.stop()
        """Download data from GUI."""
        default_filename = 'data/CD_' + datetime.now().strftime("%Y%m%d-%H%M%S")
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save data file", default_filename, "CSV Files (*.csv)")
        if filename:
            # data_to_save = list(zip(self.data_to_save, self.x_storage, self.y_storage))
            data_to_save = list(itertools.zip_longest(self.w22.threadX, self.w22.threadY, self.x_storage, self.y_storage, self.pyqtTimerTime, self.w22.windowFlagList))
            #create headers for file
            header1 = "FES Amp = " + str(self.committedAmp_lbl.value())
            header2 = "FES Dur = " + str(self.committedDur_lbl.value())
            header3 = "FES F = " + str(self.committedF_lbl.value())
            header4 = "FES Np = " + str(self.committedNp_lbl.value())
            header5 = "Thread Time (s), Thread Voltage (V), GUI Time (s), GUI Voltage (V), Inner Loop Time (s), Window Flag"
            #save data to file
            np.savetxt(filename, data_to_save, delimiter=',', fmt='%s', comments = '', 
                header = '\n'.join([header1, header2, header3, header4, header5]))
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setText("Download completed successfully!")
            msg.setWindowTitle("Success")
            msg.exec()
        self.timer.start()

    def pause_plotting(self):
        """Pause plotting by stopping the bacgkround timer."""
        if self.pause_tb.isChecked():
            self.timer.stop()
        else:
            self.timer.start()

    def key_press_event(self, event):
        """Handle key press event."""
        if event.key() == Qt.Key_Escape:
            self.close()


# THREAD FOR DATA LOGGING:
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
class DataLoggingThread(pg.QtCore.QThread):
    newData = pg.QtCore.Signal(list)
    def run(self):
        while True:
            time.sleep(THREAD_SPEED)
            if ADC_ENABLED:
                x = float(time.time())
                y = float(myADC.voltage)
            else:
                # do NOT plot data from here!
                x = float(time.time())
                y = float(np.random.random())
            self.newData.emit([x, y])

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
    ads.data_rate = 860
    # Create single-ended input on channel 0
    myADC = AnalogIn(ads, ADS.P0)
else:
    myADC = None

w = Window1(myFES, myADC)
w.show()
myFES.close()
sys.exit(app.exec_())
