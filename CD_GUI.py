# IMPORTS
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
#PyQt Imports
from PyQt5 import QtWidgets, QtCore, uic, QtTest
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
from threading import Thread
#FES Imports
from dkc_rehamovelib.DKC_rehamovelib import *  # Import our library


# INITIALIZE VARIABLES
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
ADC_ENABLED = False

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
        # myFES = Rehamove_DKC(str(self.comports[self.portSelect_cb.currentIndex()].device)); # Open USB port (on Windows) -- maybe will want a dropdown
        # myFES.port = "COM6" #specific to port /dev/ttyUSB0
        myFES.port = str(self.comports[self.portSelect_cb.currentIndex()].device)
        myFES.connect()
        myFES.initialize()
        if myFES.is_connected():
            self.connect_lbl.setText('Successful')
            self.connect_lbl.setStyleSheet('color: Green')
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
        self.amp_sp.setRange(0, 150)  # FES amplitude (mA)
        self.amp_sp.setValue(30)
        self.dur_sp.setRange(0, 600)  # FES duration (us)
        self.dur_sp.setValue(500)
        self.f_sp.setRange(0, 100)  # FES frequency (Hz)
        self.f_sp.setValue(1)
        self.np_sp.setRange(0, 20)  # FES number of pulses (int)
        self.np_sp.setValue(1)

        # Connect push and check buttons
        # commit parameters to FES system
        self.commit_pb.clicked.connect(self.update_lcd)
        self.target_cb.toggled.connect(self.update_target)  # add target line to plot
        self.download_pb.clicked.connect(self.download)  # download data
        self.sendPulse_pb.clicked.connect(self.update_and_send_pulse_fes)  # send a single FES burst
        self.maxTorqueReset_pb.clicked.connect(self.reset_torque_lcd)  # reset max Torque LCD
        # self.resetBaseline_pb.clicked.connect(self.reset_baseline)  # reset max Torque LCD
        self.CD_pb.clicked.connect(self.connect_to_Window3)  # go to CD window
        self.PDRamp_pb.clicked.connect(self.connect_to_Window4)  # go to PD Ramp window

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
        
        # Setup current and max torque lcd
        self.max_torque_reached = 0.0
        self.maxTorque_lcd.display(self.max_torque_reached)
        # self.current_torque = 0.0
        # self.baseline_offset = 0.0
        # self.currentTorque_lcd.display(self.current_torque)

        # Create a plot window
        self.graphWidget = pg.PlotWidget()
        self.findChild(QWidget, "TorquePlot").layout().addWidget(self.graphWidget)
        self.graphWidget.setBackground('w')
        self.graphWidget.setTitle("Central Drive Estimation")
        self.graphWidget.setLabel('left', 'Torque (ft-lbs)')
        self.graphWidget.setLabel('bottom', 'Time (s)')
        self.graphWidget.showGrid(x=False, y=True)
        # self.graphWidget.setYRange(0, 10, padding=1)
        self.graphWidget.enableAutoRange(axis = 'y')
        self.graphWidget.setAutoVisible(y = True)
        self.graphWidget.addLegend()

        # Prepare scrolling line
        pen1 = pg.mkPen(color=([228, 26, 28]), width=2.5)
        self.data_line1 = self.graphWidget.plot(self.x, self.y, pen=pen1, name="Torque Sensor")

        #### Setup Timer ####
        self.timer = QtCore.QTimer()
        self.timer.setInterval(10)
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
            self.target = pg.InfiniteLine(movable=True, angle=0, pen={'color': 'b', 'width': 10}, label='Torque Target ={value:0.2f}',
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

        self.graphWidget.setXRange(self.x[-1]-10, self.x[-1]+2.5)
        self.data_line1.setData(self.x, self.y)

        # self.current_torque = temp_y - self.baseline_offset
        # self.currentTorque_lcd.display(self.current_torque)

        if temp_y > self.max_torque_reached:
            self.max_torque_reached = temp_y
            self.maxTorque_lcd.display(temp_y)

        # Display Current Torque 
        self.currentTorque_lcd.display(np.round(temp_y, 1))

    def add_data(self, data_buffer, new_data):
        """Store new data in buffer."""
        data_buffer = data_buffer[1:]
        data_buffer.append(float(new_data))
        return data_buffer

    def reset_torque_lcd(self):
        """Reset max torque lcd to 0"""
        self.max_torque_reached = 0.0
        self.maxTorque_lcd.display(0.0)

    # def reset_baseline(self):
    #     """Reset baseline to 0"""
    #     self.baseline_offset = self.current_torque

    #### FES METHODS ####
    # def try_fes(self):
    #     """If FES is enabled, update values and send a pulse."""
    #     if self.fesEnable_cb.isChecked():
    #         self.update_and_send_pulse_fes()
    #     else:
    #         pass

    def update_and_send_pulse_fes(self):
        """Update FES parameters and send pulse."""
        amp = int(self.committedAmp_lbl.value())  # [mA]
        dur = int(self.committedDur_lbl.value())  # [us]
        f = int(self.committedF_lbl.value())  # hz
        n_pulse = int(self.committedNp_lbl.value())

        if self.fesEnable_cb.isChecked():
            try:
                # for channels: 1 = red, 2 = blue, 3 = black, 4 = white
                channelNum = int(self.channel_cb.currentText()[0])
                for i in range(0, n_pulse):
                    myFES.write_pulse(channelNum, [(int((dur)/2),amp), (int((dur)/2), -amp)])  
                    print('Hasomed Pulse Sent')
                    QtTest.QTest.qWait(1000*(1.0/f))
            except:
                print('Failed FES Pulse')

    # def send_pulse_fes(self, amp, dur, f, n_pulse, channelNum):
    #     """Send pulse to FES."""
    #     for i in range(0, n_pulse):
    #         # Send pulse every second
    #         myFES.write_pulse(channelNum, [(int((dur)/2),amp), (int((dur)/2), -amp)])  
    #         print('Hasomed Pulse Sent')
    #         QtTest.QTest.qWait(1000*(1.0/f))

    #### MISCELLANEOUS METHODS ####
    def connect_to_Window3(self):
        """Connect to Window3."""
        self.w3 = Window3(self)
        self.windowFlag = 1
        self.close()
        self.w3.show()

    def connect_to_Window4(self):
        """Connect to Window3."""
        self.w4 = Window4(self)
        self.windowFlag = 2
        self.close()
        self.w4.show()

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
        self.committedAmp_lbl.display(self.w22.committedAmp_lbl.value())  # FES amplitude (mA)
        self.committedDur_lbl.display(self.w22.committedDur_lbl.value())  # FES Duration (us)
        self.committedF_lbl.display(self.w22.committedF_lbl.value())  # FES frequency (Hz)
        self.committedNp_lbl.display(self.w22.committedNp_lbl.value()) # FES number of pulses (int)
        
        # Connect push buttons and spinners
        self.target_cb.toggled.connect(self.update_target)
        self.download_pb.clicked.connect(self.download)
        self.returnToMain_pb.clicked.connect(self.connect_to_main)
        # self.returnToMain_pb.setStyleSheet("background-color : Green")
        self.maxTorqueReset_pb.clicked.connect(self.reset_torque_lcd)

        # Timer Bool for Run_CD_Test
        self.cd_test_timeout = 1

        #### Setup PYQTGRAPH ####
        # Preassign data
        # self.x = list(range(SAMPLES))
        self.x = [0] * SAMPLES
        self.y = [0] * SAMPLES
        self.x_storage = [0]
        self.y_storage = [0]
        self.fes_pulse_sent_idx = 0

        # Setup max torque lcd
        self.max_torque_reached = 0.0
        self.maxTorque_lcd.display(self.max_torque_reached)

        # Create a plot window
        self.graphWidget = pg.PlotWidget()
        self.findChild(QWidget, "TorquePlot").layout().addWidget(self.graphWidget)
        self.graphWidget.setBackground('w')
        self.graphWidget.setTitle("Central Drive Estimation")
        self.graphWidget.setLabel('left', 'Torque (ft-lbs)')
        self.graphWidget.setLabel('bottom', 'Samples')
        self.graphWidget.showGrid(x=False, y=True)
        self.graphWidget.enableAutoRange(axis = 'y')
        self.graphWidget.setAutoVisible(y = True)
        self.graphWidget.addLegend()

        # Prepare scrolling line
        pen1 = pg.mkPen(color=([228, 26, 28]), width=2.5)
        self.data_line1 = self.graphWidget.plot(self.x, self.y, pen=pen1, name="Torque Sensor")

        #### Setup Timer ####
        self.timer = QtCore.QTimer()
        self.timer.setInterval(10)
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
            self.target = pg.InfiniteLine(movable=True, angle=0, pen={'color': 'b', 'width': 10}, label='Torque Target ={value:0.2f}',
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

        self.graphWidget.setXRange(self.x[-1]-10, self.x[-1]+2.5)
        self.data_line1.setData(self.x, self.y)

        if temp_y > self.max_torque_reached: #update max torque lcd if new max reached
            self.max_torque_reached = temp_y
            self.maxTorque_lcd.display(temp_y)

        # Display Current Torque 
        self.currentTorque_lcd.display(np.round(temp_y, 1))

        # Run Central Drive Test 
        #25% MVC
        if self.cb_25.isChecked():
            if self.cd_test_timeout:
                self.cd_test_timer = time.time()
                self.cd_test_timeout = 0
            self.run_CD_test(temp_x, 0.25)
        #50% MVC
        if self.cb_50.isChecked():
            if self.cd_test_timeout:
                self.cd_test_timer = time.time()
                self.cd_test_timeout = 0
            self.run_CD_test(temp_x, 0.5)
        #75% MVC
        if self.cb_75.isChecked():
            if self.cd_test_timeout:
                self.cd_test_timer = time.time()
                self.cd_test_timeout = 0
            self.run_CD_test(temp_x, 0.75)
        #100% MVC
        if self.cb_100.isChecked():
            if self.cd_test_timeout:
                self.cd_test_timer = time.time()
                self.cd_test_timeout = 0
            self.run_CD_test(temp_x, 1)
      
    def run_CD_test(self, temp_x, perc):
        if (time.time() - self.cd_test_timer) < 5:
            MFGA = self.mfga_sp.value()
            SSVAR = self.variance_sp.value()

            #detect if steady state is reached
            rollingVar = np.var(self.y_storage[-50:])
            rollingMean = np.mean(self.y_storage[-50:])
            if rollingVar < SSVAR and rollingMean > 0.9*(perc*MFGA) and rollingMean < 1.1*(perc*MFGA):
                self.update_and_send_pulse_fes()     
                self.target = pg.InfiniteLine(movable=False, angle=90, pen={'color': 'g', 'width': 2.5}, bounds =[0,100], pos = temp_x)
                self.graphWidget.addItem(self.target)
                self.fes_pulse_sent_idx = temp_x
                self.reset_cd_checkboxes()
        else: 
            self.reset_cd_checkboxes()
            print('Unsuccessful Trial (Try Increasing Variance)')

    def reset_cd_checkboxes(self):
        """Reset checkboxes and timer for central drive testing."""
        self.cb_25.setChecked(False)
        self.cb_50.setChecked(False)
        self.cb_75.setChecked(False)
        self.cb_100.setChecked(False)
        self.cd_test_timeout = 1
        # self.graphWidget.removeItem(self.cd_target)

    def add_data(self, data_buffer, new_data):
        """Store new data in buffer."""
        data_buffer = data_buffer[1:]
        data_buffer.append(float(new_data))
        return data_buffer

    def reset_torque_lcd(self):
        """Reset max torque lcd to 0"""
        self.max_torque_reached = 0.0
        self.maxTorque_lcd.display(0.0)
        
    #### FES METHODS ####
    def update_and_send_pulse_fes(self):
        """Update FES parameters and send pulse."""
        amp = int(self.w22.committedAmp_lbl.value())  # [mA]
        dur = int(self.w22.committedDur_lbl.value())  # [us]
        f = int(self.w22.committedF_lbl.value())  # hz
        n_pulse = int(self.w22.committedNp_lbl.value())
        channelNum = int(self.w22.channel_cb.currentText()[0])

        if self.w22.fesEnable_cb.isChecked():
            try:
                # for channels: 1 = red, 2 = blue, 3 = black, 4 = white
                for i in range(0, n_pulse):
                    myFES.write_pulse(channelNum, [(int((dur)/2),amp), (int((dur)/2), -amp)])  
                    print('Hasomed Pulse Sent')
                    QtTest.QTest.qWait(1000*(1.0/f))
            except:
                print('Failed FES Pulse')

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
            header5 = "FES Pulse Delivered at = " + str(self.fes_pulse_sent_idx)
            header6 = "Thread Time (s), Thread Voltage (V), GUI Time (s), GUI Voltage (V), Inner Loop Time (s), Window Flag"
            #save data to file
            np.savetxt(filename, data_to_save, delimiter=',', fmt='%s', comments = '', 
                header = '\n'.join([header1, header2, header3, header4, header5, header6]))
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

# PD RAMP WINDOW:
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
class Window4(QtWidgets.QMainWindow):
    def __init__(self, w2, *args, **kwargs):
        super(Window4, self).__init__(*args, **kwargs)
        uic.loadUi('resources/_CD_GUI_PDRamp_Formed.ui',
                   self)  # load ui from Qt Designer

        #### Initialize Variables ####
        self.w22 = w2
        self.test_complete = False
        self.time_start = time.time()
        self.pyqtTimerTime = [0]

        #### Setup GUI Widgets ####
        # Grab values commited to Hasomed Device from Window2
        self.channel_lbl.setText(self.w22.channel_cb.currentText())
        self.committedAmp_lbl.display(150)  # FES amplitude (mA)
        self.committedDur_lbl.display(50)  # FES Duration (us)
        self.committedF_lbl.display(1)  # FES frequency (Hz)
        self.committedNp_lbl.display(1) # FES number of pulses (int)

        ##TO DO
        self.currentChannel = int(self.w22.channel_cb.currentText()[0]) #CHANGE THIS TO BE A VISUAL INDICATOR
        self.pulse_sent_flag =  True #change to be switched by button
        ##

        # Connect push buttons and spinners
        self.target_cb.toggled.connect(self.update_target)
        self.download_pb.clicked.connect(self.download)
        self.returnToMain_pb.clicked.connect(self.connect_to_main)
        self.maxTorqueReset_pb.clicked.connect(self.reset_torque_lcd)
        
        # Setup push button and bool for PD Ramp
        # self.beginTest_pb.clicked.connect(self.set_pd_ramp_start_bool)
        self.beginTest_pb.clicked.connect(self.pd_ramp)
        self.pd_ramp_start_bool = False
        self.pd_ramp_end_bool = True

        #### Setup PYQTGRAPH ####
        # Preassign data
        # self.x = list(range(SAMPLES))
        self.x = [0] * SAMPLES
        self.y = [0] * SAMPLES
        self.x_storage = [0]
        self.y_storage = [0]
        self.fes_pulse_sent_idx = 0

        # Setup max torque lcd
        self.max_torque_reached = 0.0
        self.maxTorque_lcd.display(self.max_torque_reached)

        # Create a plot window
        self.graphWidget = pg.PlotWidget()
        self.findChild(QWidget, "TorquePlot").layout().addWidget(self.graphWidget)
        self.graphWidget.setBackground('w')
        self.graphWidget.setTitle("Pulse Duration Ramp")
        self.graphWidget.setLabel('left', 'Torque (ft-lbs)')
        self.graphWidget.setLabel('bottom', 'Samples')
        self.graphWidget.showGrid(x=False, y=True)
        self.graphWidget.enableAutoRange(axis = 'y')
        self.graphWidget.setAutoVisible(y = True)
        self.graphWidget.addLegend()

        # Prepare scrolling line
        pen1 = pg.mkPen(color=([228, 26, 28]), width=2.5)
        self.data_line1 = self.graphWidget.plot(self.x, self.y, pen=pen1, name="Torque Sensor")

        #### Setup Timer ####
        self.timer = QtCore.QTimer()
        self.timer.setInterval(10)
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
            self.target = pg.InfiniteLine(movable=True, angle=0, pen={'color': 'b', 'width': 10}, label='Torque Target ={value:0.2f}',
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

        self.graphWidget.setXRange(self.x[-1]-10, self.x[-1]+2.5)
        self.data_line1.setData(self.x, self.y)

        if temp_y > self.max_torque_reached: #update max torque lcd if new max reached
            self.max_torque_reached = temp_y
            self.maxTorque_lcd.display(temp_y)

        # Display Current Torque 
        self.currentTorque_lcd.display(np.round(temp_y, 1))

        # Begin Pulse Duration Ramp
        if self.pd_ramp_start_bool:
            self.beginTest_pb.setStyleSheet("border: 2px black; border-radius: 5px; padding: 5.5px; background: green")
            if self.pd_ramp_end_bool:
                self.pd_ramp_timer = time.time()
                self.pd_ramp_end_bool = False
            self.pulse_duration_ramp()

    # def pd_ramp_calling_func(self):
    #     for k, dur in enumerate(range(50, 650, 50)):
    #         self.pd_ramp(dur)
    #         self.pdramp_progbar.setValue(100*(k/12))
    #     self.pdramp_progbar.setValue(0)
    #     self.beginTest_pb.setStyleSheet("")

    # def pd_ramp(self, dur):
    #     """Send pulse to FES."""
    #     self.beginTest_pb.setStyleSheet("border: 2px black; border-radius: 5px; padding: 5.5px; background: green")
    #     amp = 150
    #     channelNum = self.currentChannel
    #     # for k, dur in enumerate(range(50, 650, 50)):
    #     print(dur)
    #     # Send pulse every second
    #     myFES.write_pulse(channelNum, [(dur, amp), (50, 0), (dur, -amp)])
    #     print('Hasomed Pulse Sent')
    #     QTimer.singleShot(3000, lambda: self.pd_ramp_calling_func)
        

    def pd_ramp(self):
        """Send pulse to FES."""
        self.beginTest_pb.setStyleSheet("border: 2px black; border-radius: 5px; padding: 5.5px; background: green")
        amp = 30
        channelNum = self.currentChannel
        for k, dur in enumerate(range(50, 650, 50)):
            print(dur)
            # Send pulse every second
            self.send_single_pulse_fes(channelNum, amp, dur)
            self.committedDur_lbl.display(dur)  # FES Duration (us)
            self.pdramp_progbar.setValue(100*(k/11))
            print('Hasomed Pulse Sent')
            QtTest.QTest.qWait(1000)
        self.pdramp_progbar.setValue(0)
        self.beginTest_pb.setStyleSheet("")

    # def pulse_duration_ramp(self):
    #     time_elapsed_since_start = (time.time() - self.pd_ramp_timer)
    #     """Need to figure out how to get this to only send one pulse."""
    #     if 3 < time_elapsed_since_start < 6 and self.pulse_sent_flag:
    #         self.send_single_pulse_fes(150, 50, self.currentChannel)
    #         self.pdramp_progbar.setValue(100*(1/12))
    #         self.pulse_sent_flag = False
    #     if 6 < time_elapsed_since_start < 9:
    #         self.send_single_pulse_fes(150, 100, self.currentChannel)
    #         self.pdramp_progbar.setValue(100*(2/12))
    #     if 9 < time_elapsed_since_start < 12:
    #         self.send_single_pulse_fes(150, 150, self.currentChannel)
    #         self.pdramp_progbar.setValue(100*(3/12))       
    #     if 12 < time_elapsed_since_start < 15:
    #         self.send_single_pulse_fes(150, 200, self.currentChannel)
    #         self.pdramp_progbar.setValue(100*(4/12))       
    #     if 15 < time_elapsed_since_start < 18:
    #         self.send_single_pulse_fes(150, 250, self.currentChannel)
    #         self.pdramp_progbar.setValue(100*(5/12))       
    #     if 18 < time_elapsed_since_start < 21:
    #         self.send_single_pulse_fes(150, 300, self.currentChannel)
    #         self.pdramp_progbar.setValue(100*(6/12))
    #     if 21 < time_elapsed_since_start < 24:
    #         self.send_single_pulse_fes(150, 350, self.currentChannel)
    #         self.pdramp_progbar.setValue(100*(7/12))
    #     if 24 < time_elapsed_since_start < 27:
    #         self.send_single_pulse_fes(150, 400, self.currentChannel)
    #         self.pdramp_progbar.setValue(100*(8/12))
    #     if 27 < time_elapsed_since_start < 30:
    #         self.send_single_pulse_fes(150, 450, self.currentChannel)
    #         self.pdramp_progbar.setValue(100*(9/12))
    #     if 30 < time_elapsed_since_start < 33:
    #         self.send_single_pulse_fes(150, 500, self.currentChannel)
    #         self.pdramp_progbar.setValue(100*(10/12))
    #     if 33 < time_elapsed_since_start < 36:
    #         self.send_single_pulse_fes(150, 550, self.currentChannel)
    #         self.pdramp_progbar.setValue(100*(11/12))
    #     if 36 < time_elapsed_since_start < 39:
    #         self.send_single_pulse_fes(150, 600, self.currentChannel)
    #         self.pdramp_progbar.setValue(100*(12/12))
    #     if time_elapsed_since_start > 42:
    #         self.pdramp_progbar.setValue(0)
    #         self.pd_ramp_start_bool = False
    #         self.pd_ramp_end_bool = True
    #         self.beginTest_pb.setStyleSheet("")

    def set_pd_ramp_start_bool(self):
        self.pd_ramp_start_bool = True

    def add_data(self, data_buffer, new_data):
        """Store new data in buffer."""
        data_buffer = data_buffer[1:]
        data_buffer.append(float(new_data))
        return data_buffer

    def reset_torque_lcd(self):
        """Reset max torque lcd to 0"""
        self.max_torque_reached = 0.0
        self.maxTorque_lcd.display(0.0)
        
    #### FES METHODS ####
    def send_single_pulse_fes(self, channelNum, amp, dur):
        """Send single pulse to FES."""
        if self.w22.fesEnable_cb.isChecked(): 
            myFES.write_pulse(channelNum, [(int((dur)/2),amp), (int((dur)/2), -amp)])  
            print('Hasomed Pulse Sent')

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
            header5 = "FES Pulse Delivered at = " + str(self.fes_pulse_sent_idx)
            header6 = "Thread Time (s), Thread Voltage (V), GUI Time (s), GUI Voltage (V), Inner Loop Time (s), Window Flag"
            #save data to file
            np.savetxt(filename, data_to_save, delimiter=',', fmt='%s', comments = '', 
                header = '\n'.join([header1, header2, header3, header4, header5, header6]))
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
                y = float((myADC.voltage*-95.64) + 113.3) #multiply by 1.3558 for Nm
            else:
                # do NOT plot data from here!
                x = float(time.time())
                y = float(np.sin(x) + 0.1*np.random.random())
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
