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
from pprint import pprint

# INITIALIZE VARIABLES
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
ADC_ENABLED = True

if ADC_ENABLED:
    import busio
    import board
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    THREAD_SPEED = 0
else:
    THREAD_SPEED = 0.001

SAMPLES = 1000
SAMPLES_ = 100
DATA_NB = 1
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"


# WINDOW: LANDING PAGE
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
class ConnectWindow(QDialog):
    def __init__(self, myFES, myADC, *args, **kwargs):
        super().__init__(*args, **kwargs)
        uic.loadUi('resources/_CD_GUI_Landing_Formed_Clinician.ui', self)

        # find existing COM Ports
        self.comports = serial.tools.list_ports.comports(include_links=True)
        for comport in self.comports:
            self.portSelect_cb.addItem(comport.device)
        self.startPlotting_pb.clicked.connect(self.connect_to_main)

    def key_press_event(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()

    def connect_to_main(self):
        # myFES = Rehamove_DKC(str(self.comports[self.portSelect_cb.currentIndex()].device)); # Open USB port (on Windows) -- maybe will want a dropdown
        # myFES.port = "COM6" #specific to port /dev/ttyUSB0
        if not self.ignoreFES_cb.isChecked():
            myFES.port = str(self.comports[self.portSelect_cb.currentIndex()].device)
            myFES.connect()
            myFES.initialize()
        if myFES.is_connected() and self.identifier_lbl.toPlainText() and (self.pSide_cb.isChecked() or self.npSide_cb.isChecked()) or self.ignoreFES_cb.isChecked():
            self.connect_lbl.setText('Successful')
            self.connect_lbl.setStyleSheet('color: Green')
            self.mw = DebugWindow(myFES, myADC)
            self.mw.comport_lbl.setText(self.comports[self.portSelect_cb.currentIndex()].device)
            self.mw.participantID_lbl.setText(self.identifier_lbl.toPlainText())
            if self.pSide_cb.isChecked():
                self.mw.testingSide_lbl.setText('P')
            if self.npSide_cb.isChecked():
                self.mw.testingSide_lbl.setText('NP')
            self.mw.currentDate = self.date_de.date().toPyDate()
            if self.ignoreFES_cb.isChecked():
                self.mw.comport_lbl.setText('No Port Connected')
                self.mw.participantID_lbl.setText('MXXX')
                self.mw.testingSide_lbl.setText('None')
            self.mw.show()
            self.close()
        elif not self.identifier_lbl.toPlainText():
            self.identifier_lbl.setPlaceholderText('Please add Participant ID!')
            self.identifier_lbl.setStyleSheet('color: red')
        elif not (self.pSide_cb.isChecked() or self.npSide_cb.isChecked()):
            self.connect_lbl.setText('Please choose a testing side!')
            self.connect_lbl.setStyleSheet('color: red')
        else:  
            self.connect_lbl.setText('Unsuccessful Connection: Try Different Port')
            self.connect_lbl.setStyleSheet('color: red')
# MAIN WINDOW:
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# https://www.youtube.com/watch?v=XXPNpdaK9WA
class DebugWindow(QtWidgets.QMainWindow):
    def __init__(self, myFES, myADC, *args, **kwargs):
        super(DebugWindow, self).__init__(*args, **kwargs)
        uic.loadUi('resources/_CD_GUI_Main_Clinician_Formed.ui',
                   self)  # load ui from Qt Designer

        #### Setup Quitting Callback ####
        self.app = QtWidgets.QApplication.instance()
        self.app.aboutToQuit.connect(self.about_to_quit)
        self.showMaximized()
        #### Setup GUI Widgets ####
        # Setup FES Channels and Parameters
        self.channel_cb.addItems(['', '1 (Red)', '2 (Blue)', '3 (Black)', '4 (White)'])
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
        self.commited_pb_pressed_bool = 0 #set to 1 once button is pressed once (for error reporting)
        self.target_cb.toggled.connect(self.update_target)  # add target line to plot
        self.download_pb.clicked.connect(self.download)  # download data
        self.sendPulse_pb.clicked.connect(self.process_fes_request)  # send a single FES burst
        self.maxTorqueReset_pb.clicked.connect(self.reset_torque_lcd)  # reset max Torque LCD
        self.beginTesting_pb.clicked.connect(self.connect_to_ActivationWindow)  # go to Activation MVC window

        #### Initialize Variables ####
        self.time_start = time.time()
        self.max_value_reached = 0
        self.threadX = [0]
        self.threadY = [0]
        self.windowFlag = 0 #0 if Window 2, 1 if Window 3
        self.windowFlagList = []
        self.pulseSent_bool = 0
        self.mw_pulse_sent_idx = []

        #### Setup Error Reporting ####
        self.error_dialog = QtWidgets.QErrorMessage()

        #### Setup PYQTGRAPH ####
        # Preassign data
        self.x = [0] * SAMPLES #list(range(SAMPLES))
        self.y = [0] * SAMPLES
        self.x_storage = []
        self.y_storage = []
        self.pyqtTimerTime = []
        
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
        self.thread = DataLoggingThread(parent = self)
        self.thread.newData.connect(self.thread_update)
        self.thread.start()

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
        self.commited_pb_pressed_bool = 1 #set to 1 once button is pressed once
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
        self.pulseSent_bool = 0 

    def add_data(self, data_buffer, new_data):
        """Store new data in buffer."""
        data_buffer = data_buffer[1:]
        data_buffer.append(float(new_data))
        return data_buffer

    def reset_torque_lcd(self):
        """Reset max torque lcd to 0"""
        self.max_torque_reached = 0.0
        self.maxTorque_lcd.display(0.0)

    def process_fes_request(self):
        """Update FES parameters and send pulse."""
        amp = int(self.committedAmp_lbl.value())  # [mA]
        dur = int(self.committedDur_lbl.value())  # [us]
        f = int(self.committedF_lbl.value())  # [Hz]
        n_pulse = int(self.committedNp_lbl.value())

        if self.fesEnable_cb.isChecked():
            for i in range(0, n_pulse):
#                 QTimer.singleShot(1000* i * (1.0/f - (dur*(10**-6))), self.send_fes_pulse) #instantiate n_pulse times each with timeout equal to frequency delay
                QTimer.singleShot(int(1000* i * (1/f)), self.send_fes_pulse) #instantiate n_pulse times each with timeout equal to frequency delay

    def send_fes_pulse(self):
        amp = int(self.committedAmp_lbl.value())  # [mA]
        dur = int(self.committedDur_lbl.value())  # [
        
        #for channels: 1 = red, 2 = blue, 3 = black, 4 = white
        try:
            # for channels: 1 = red, 2 = blue, 3 = black, 4 = white
            channelNum = int(self.channel_cb.currentText()[0])
            myFES.write_pulse(channelNum, [(int((dur)/2),amp), (int((dur)/2), -amp)])  
            self.mw_pulse_sent_idx.append(len(self.threadX)) #store FES idx for Main Window
        except:
            self.error_dialog.showMessage('Stimulation not delivered, double check (1) channel is selected, and (2) that electrodes are connected.')


    #### MISCELLANEOUS METHODS ####          
    def connect_to_ActivationWindow(self):
        """Connect to Activation MVC Window."""
        if not self.channel_cb.currentText():
            self.error_dialog.showMessage("Error: No stimulation channel selected!") 
        else:           
            self.w5 = ActivationWindow(self)
            self.windowFlag = 1
            self.close()
            self.w5.show()

    def download(self):
        self.timer.stop()
        """Download data from GUI."""
        default_filename = 'data/' + 'Central_Drive_' + self.participantID_lbl.text() + '_' + str(self.currentDate.strftime("%Y%m%d")) + '_DebugWindow'
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save data file", default_filename, "CSV Files (*.csv)")
        if filename:
            # data_to_save = list(zip(self.data_to_save, self.x_storage, self.y_storage))
            data_to_save = list(itertools.zip_longest(self.threadX, self.threadY, self.x_storage, self.y_storage, self.pyqtTimerTime, self.windowFlagList, self.pulseSent_array))
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

    def about_to_quit(self): 
        #if things start going wrong remove self. from all DataLoggingThread definitions
        """This is called whenever anyone presses the X at the top of any window"""
        # os.system('cls') #clear terminal 
        print('Exiting Application')
        self.thread.terminate()
        self.timer.stop()
        sys.exit()
        QCoreApplication.quit()

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
class CDWindow(QtWidgets.QMainWindow):
    def __init__(self, mw, *args, **kwargs):
        super(CDWindow, self).__init__(*args, **kwargs)
        uic.loadUi('resources/_CD_GUI_CDTest_Formed_Clinician.ui',
                   self)  # load ui from Qt Designer

        #### Initialize Variables ####
        self.mw2 = mw.mw2
        self.showMaximized()
        self.test_complete = False
        self.time_start = time.time()
        self.pyqtTimerTime = [0]
        self.window_time_start_idx = len(self.mw2.threadX) #index of first point in threadX so export everything after this for just this Window
        self.successful_test_counter = 0

        #### Setup GUI Widgets ####
        # Grab values commited to Hasomed Device from DebugWindow
        self.channel_lbl.setText(self.mw2.channel_cb.currentText())
        self.committedAmp_lbl.display(150)  # FES amplitude (mA)
        self.committedDur_lbl.display(self.mw2.chosenDuration)  # FES Duration (us)
        self.committedF_lbl.display(100)  # FES frequency (Hz)
        self.committedNp_lbl.display(15) # FES number of pulses (int)
        self.successfulTestCounter_lcd.display(self.successful_test_counter)

        #Setup Auto CD Parameters
        try:
            self.mfga_sp.setValue(self.mw2.activation_MVC * 0.8)
            self.variance_sp.setValue(0.1)
        except:
            self.mfga_sp.setValue(0)
            self.variance_sp.setValue(0)           
        
        # Connect push buttons and spinners
        self.target_cb.toggled.connect(self.update_target)
        self.download_pb.clicked.connect(self.download)
        self.returnToMain_pb.clicked.connect(self.download)
        self.returnToMain_pb.clicked.connect(self.connect_to_main)
        self.maxTorqueReset_pb.clicked.connect(self.reset_torque_lcd)
        self.beginTest_pb.setCheckable(True)
        # Timer Bool for Run_CD_Test
        self.cd_test_timeout = 1

        #### Setup Error Reporting ####
        self.error_dialog = QtWidgets.QErrorMessage()

        #### Setup PYQTGRAPH ####
        # Preassign data
        # self.x = list(range(SAMPLES))
        self.x = [0] * SAMPLES
        self.y = [0] * SAMPLES
        self.x_storage = []
        self.y_storage = []
        self.fes_pulse_sent_idx = [] #array to store idx's of any FES pulses delivered

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
        temp_x = self.mw2.threadX[-1]
        temp_y = self.mw2.threadY[-1]
        
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
        #100% MVC
        if self.beginTest_pb.isChecked():
            self.beginTest_pb.setStyleSheet("background-color: yellow")
            if self.cd_test_timeout: #can likely optimize in the future with 
                self.cd_test_timer = time.time()
                self.cd_test_timeout = 0
            self.run_CD_test(temp_x, 1)
      
    def run_CD_test(self, temp_x, perc):
        if (time.time() - self.cd_test_timer) < 10:
            MFGA = self.mfga_sp.value()
            SSVAR = self.variance_sp.value()

            #find which indices correspond to x ms back
            window_size = 0.25 #[s]
            current_idx_subset = np.array(self.x_storage[-1]) - np.array(self.x_storage[-1000:]) #take subset we know is definitely within x ms
            correct_idx = np.argmax(current_idx_subset[::-1] > window_size) #idx matching window size (but not correct relative to actual position in x_storage)

            #detect if steady state is reached
            rollingVar = np.var(self.y_storage[-correct_idx - 1:]) #look back at last "window_size" seconds as window
            rollingMean = np.mean(self.y_storage[-correct_idx - 1:]) #look back at last "window_size" seconds as window
            
            if rollingVar < SSVAR and rollingMean > MFGA: #and rollingMean < 1.1*(perc*MFGA):
                self.process_fes_request()
                try:
                    self.graphWidget.removeItem(self.marker)
                except:
                    pass
                self.marker = pg.InfiniteLine(movable=False, angle=90, pen={'color': 'black', 'width': 2.5}, bounds =[0,100], pos = self.mw2.threadX[-1])
                self.graphWidget.addItem(self.marker)
                self.reset_cd_checkboxes()
                self.successful_test_counter += 1 #increment sucessful test counter and display
                self.successfulTestCounter_lcd.display(self.successful_test_counter)
                self.beginTest_pb.setStyleSheet("background-color: rgb(0, 170, 255)")

        else: 
            self.reset_cd_checkboxes()
            self.beginTest_pb.setStyleSheet("background-color: rgb(0, 170, 255)")
            self.error_dialog.showMessage('Unsuccessful Trial (Try Decreasing MFGA or Increasing Variance)')

    def reset_cd_checkboxes(self):
        """Reset checkboxes and timer for central drive testing."""
        self.beginTest_pb.toggle() 
        self.cd_test_timeout = 1

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
    def process_fes_request(self):
        channelNum = int(self.mw2.channel_cb.currentText()[0])
        myFES.set_amp(int(self.committedAmp_lbl.value())) #setter functions
        myFES.set_dur(int(self.committedDur_lbl.value()))
        myFES.set_freq(int(self.committedF_lbl.value()))

        myFES.build_CD_pulse() #calls method within Stimulator class which has 3 pulses 
        self.mw2.mw_pulse_sent_idx.append(len(self.mw2.threadX)) #store in case download from Main Window
        self.fes_pulse_sent_idx.append(len(self.mw2.threadX)) #store index when FES pulse sent

        myFES.write_pulse(channelNum, myFES.message_CD)
        myFES.write_pulse(channelNum, myFES.message_CD)
        myFES.write_pulse(channelNum, myFES.message_CD)
        myFES.write_pulse(channelNum, myFES.message_CD)
        myFES.write_pulse(channelNum, myFES.message_CD)

    #### MISCELLANEOUS METHODS ####
    def connect_to_main(self):
        """Connect to main GUI."""
        self.mw2.windowFlag = 0
        self.mw2.show()
        self.close()

    def download(self):
        self.timer.stop()
        """Download data from GUI."""
        default_filename = 'data/' + 'Central_Drive_' + self.mw2.participantID_lbl.text() + '_' + str(self.mw2.currentDate.strftime("%Y%m%d")) + '_CDTest'
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save data file", default_filename, "CSV Files (*.csv)")
        if filename:
            #data_to_save = list(itertools.zip_longest(self.mw2.threadX[self.window_time_start_idx:], self.mw2.threadY[self.window_time_start_idx:], self.x_storage, self.y_storage, self.pyqtTimerTime, self.mw2.windowFlagList[self.window_time_start_idx:]))
            #slice data to only be from this specific window
            time_ = list(np.array(self.mw2.threadX[self.window_time_start_idx:])  - self.mw2.threadX[self.window_time_start_idx]) #reset time to be zero 
            torque_ = self.mw2.threadY[self.window_time_start_idx:]
            window_ = self.mw2.windowFlagList[self.window_time_start_idx:]
            fes_temp = np.zeros(len(self.mw2.threadX)) #following 3 lines create 0s for FES array
            fes_temp[self.fes_pulse_sent_idx] = 1
            fes_ = fes_temp[self.window_time_start_idx:]
            data_to_save = list(itertools.zip_longest(time_, torque_ , fes_, window_))
            #create headers for file
            header1 = "FES Amp = " + str(self.committedAmp_lbl.value())
            header2 = "FES Dur = " + str(self.committedDur_lbl.value())
            header3 = "FES F = " + str(self.committedF_lbl.value())
            header4 = "FES Np = " + str(self.committedNp_lbl.value())
            # header5 = "FES Pulse Delivered at = " + str(self.fes_pulse_sent_idx)
            # header6 = "Thread Time (s), Thread Voltage (V), GUI Time (s), GUI Voltage (V), Inner Loop Time (s), Window Flag"
            header6 = "Time (s), Torque (ft-lbs), FES Pusle, Window Flag"
            #save data to file
            # np.savetxt(filename, data_to_save, delimiter=',', fmt='%s', comments = '', 
            #     header = '\n'.join([header1, header2, header3, header4, header5, header6]))
            np.savetxt(filename, data_to_save, delimiter=',', fmt='%s', comments = '', 
                header = '\n'.join([header1, header2, header3, header4, header6]))
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
class RampWindow(QtWidgets.QMainWindow):
    def __init__(self, mw, *args, **kwargs):
        super(RampWindow, self).__init__(*args, **kwargs)
        uic.loadUi('resources/_CD_GUI_PDRamp_Formed_Clinician.ui',
                   self)  # load ui from Qt Designer

        #### Initialize Variables ####
        self.mw2 = mw.mw2 #Activation Window was last Main Window open so need to pass in its inherited classes from MW2
        self.test_complete = False
        self.time_start = time.time()
        self.pyqtTimerTime = [0]
        self.window_time_start_idx = len(self.mw2.threadX) #index of first point in threadX so export everything after this for just this Window
        self.showMaximized()

        #### Setup GUI Widgets ####
        # Grab values commited to Hasomed Device from DebugWindow
        self.channel_lbl.setText(self.mw2.channel_cb.currentText())
        self.committedAmp_lbl.display(150)  # FES amplitude (mA)
        self.committedDur_lbl.display(50)  # FES Duration (us)
        self.committedF_lbl.display(1)  # FES frequency (Hz)
        self.committedNp_lbl.display(1) # FES number of pulses (int)

        ##TO DO
        self.currentChannel = int(self.mw2.channel_cb.currentText()[0]) #CHANGE THIS TO BE A VISUAL INDICATOR
        self.pulse_sent_flag =  True #change to be switched by button
        ##

        # Connect push buttons and spinners
        self.target_cb.toggled.connect(self.update_target)
        self.download_pb.clicked.connect(self.download)
        self.returnToMain_pb.clicked.connect(self.download)
        self.returnToMain_pb.clicked.connect(self.connect_to_main)
        self.nextCDTest_pb.clicked.connect(self.download)
        self.nextCDTest_pb.clicked.connect(self.connect_to_CDTest)
        self.maxTorqueReset_pb.clicked.connect(self.reset_torque_lcd)
        
        # Setup push button and bool for PD Ramp
        self.beginTest_pb.setCheckable(True)
        self.pd_ramp_finished = 1

        #### Setup PYQTGRAPH ####
        # Preassign data
        # self.x = list(range(SAMPLES))
        self.x = [0] * SAMPLES
        self.y = [0] * SAMPLES
        self.x_storage = [0]
        self.y_storage = [0]
        self.fes_pulse_sent_idx = []

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
        temp_x = self.mw2.threadX[-1]
        temp_y = self.mw2.threadY[-1]
        
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

        # Run PD Ramp 
        if self.beginTest_pb.isChecked() and self.pd_ramp_finished == 1:
            self.pd_ramp_finished = 0
            self.pd_ramp()

    def add_data(self, data_buffer, new_data):
        """Store new data in buffer."""
        data_buffer = data_buffer[1:]
        data_buffer.append(float(new_data))
        return data_buffer

    def reset_torque_lcd(self):
        """Reset max torque lcd to 0"""
        self.max_torque_reached = 0.0
        self.maxTorque_lcd.display(0.0)

    #### PD RAMP METHODS ####
    def pd_ramp(self):
        """Send single pulse every 3 seconds for duration ramping from 50-600 us in 50us increments."""
        if self.beginTest_pb.isChecked():
            self.beginTest_pb.setStyleSheet("background-color: yellow")
            for i, dur in enumerate(range(50, 650, 50)):
                QTimer.singleShot(i * 1000, self.outer(100*((i+1)/12), dur)) 
        #     # self.beginTest_pb.setStyleSheet("color: rgb(255, 255, 255); background-color: rgb(150, 150, 150)")
        #     QTimer.singleShot(0 * 100, lambda: self.send_pd_ramp_pulse(100*(1/12), 50)) 
        #     QTimer.singleShot(3 * 100, lambda: self.send_pd_ramp_pulse(100*(2/12), 100)) 
        #     QTimer.singleShot(6 * 100, lambda: self.send_pd_ramp_pulse(100*(3/12), 150)) 
        #     QTimer.singleShot(9 * 100, lambda: self.send_pd_ramp_pulse(100*(4/12), 200)) 
        #     QTimer.singleShot(12 * 100, lambda: self.send_pd_ramp_pulse(100*(5/12), 250)) 
        #     QTimer.singleShot(15 * 100, lambda: self.send_pd_ramp_pulse(100*(6/12), 300)) 
        #     QTimer.singleShot(18 * 100, lambda: self.send_pd_ramp_pulse(100*(7/12), 350)) 
        #     QTimer.singleShot(21 * 100, lambda: self.send_pd_ramp_pulse(100*(8/12), 400)) 
        #     QTimer.singleShot(24 * 100, lambda: self.send_pd_ramp_pulse(100*(9/12), 450))
        #     QTimer.singleShot(27 * 100, lambda: self.send_pd_ramp_pulse(100*(10/12), 500))
        #     QTimer.singleShot(30 * 100, lambda: self.send_pd_ramp_pulse(100*(11/12), 550))
        #     QTimer.singleShot(33 * 100, lambda: self.send_pd_ramp_pulse(100*(12/12), 600))

    def outer(self, pbar, dur):
        """Wrapper function, this is something Philipp helped me with, and it just allows me to call a function in QTimer.singleShot()"""
        def send_pd_ramp_pulse():
            """Function called when QTimer.singleShot() from pd_ramp times out, which sends an individual pulse with specific pulse duration and progress bar percentage"""
            self.pdramp_progbar.setValue(pbar)
            amp = int(self.committedAmp_lbl.value())  # [mA]
            channelNum = int(self.mw2.channel_cb.currentText()[0])
            try:
                # for channels: 1 = red, 2 = blue, 3 = black, 4 = white
                self.target = pg.InfiniteLine(movable=False, angle=90, pen={'color': 'black', 'width': 2.5}, bounds =[0,150], pos = self.mw2.threadX[-1])
                self.graphWidget.addItem(self.target)
                myFES.write_pulse(channelNum, [(int((dur)/2), amp), (int((dur)/2), -amp)])  
                self.mw2.mw_pulse_sent_idx.append(len(self.mw2.threadX)) #store in case download from Main Window
                self.fes_pulse_sent_idx.append(len(self.mw2.threadX)) #store index when FES pulse sent
            except:
                self.error_dialog.showMessage('Stimulation not delivered, double check connection to Hasomed')
            if pbar == 100:
                self.pdramp_progbar.setValue(0)
                self.beginTest_pb.toggle()
                self.pd_ramp_finished = 1
                self.beginTest_pb.setStyleSheet("background-color: rgb(0, 170, 255)")
        return send_pd_ramp_pulse

    #### MISCELLANEOUS METHODS ####
    def connect_to_main(self):
        """Connect to main GUI."""
        self.mw2.windowFlag = 0
        self.mw2.show()
        self.close()

    def connect_to_CDTest(self):
        """Connect to main GUI."""
        # self.w3 = CDWindow(self)
        # self.windowFlag = 3
        # self.close()
        # self.w3.show()
        self.w25 = Ramp_Visualization(self)
        self.windowFlag = 2.5
        self.close()
        self.w25.show()

    def download(self):
        self.timer.stop()
        """Download data from GUI."""
        default_filename = 'data/' + 'Central_Drive_' + self.mw2.participantID_lbl.text() + '_' + str(self.mw2.currentDate.strftime("%Y%m%d")) + '_PDRamp'
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save data file", default_filename, "CSV Files (*.csv)")
        if filename:
            # data_to_save = list(itertools.zip_longest(self.mw2.threadX, self.mw2.threadY, self.x_storage, self.y_storage, self.pyqtTimerTime, self.mw2.windowFlagList))
            time_ = list(np.array(self.mw2.threadX[self.window_time_start_idx:])  - self.mw2.threadX[self.window_time_start_idx]) #reset time to be zero 
            torque_ = self.mw2.threadY[self.window_time_start_idx:]
            window_ = self.mw2.windowFlagList[self.window_time_start_idx:]
            fes_temp = np.zeros(len(self.mw2.threadX)) #following 3 lines create 0s for FES array
            fes_temp[self.fes_pulse_sent_idx] = 1
            fes_ = fes_temp[self.window_time_start_idx:]
            data_to_save = list(itertools.zip_longest(time_, torque_ , fes_, window_))

            #save data for visualization
            self.mw2.rampfes = fes_ * np.max(torque_)
            self.mw2.ramptor = torque_
            self.mw2.ramptime = time_

            #create headers for file
            header1 = "FES Amp = " + str(self.committedAmp_lbl.value())
            header2 = "FES Dur = " + str(self.committedDur_lbl.value())
            header3 = "FES F = " + str(self.committedF_lbl.value())
            header4 = "FES Np = " + str(self.committedNp_lbl.value())
            # header5 = "FES Pulse Delivered at = " + str(self.fes_pulse_sent_idx)
            # header6 = "Thread Time (s), Thread Voltage (V), GUI Time (s), GUI Voltage (V), Inner Loop Time (s), Window Flag"
            header6 = "Time (s), Torque (ft-lbs), FES Pulse, Window Flag"
            #save data to file
            np.savetxt(filename, data_to_save, delimiter=',', fmt='%s', comments = '', 
                header = '\n'.join([header1, header2, header3, header4, header6]))
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

# ACTIVATION MVC WINDOW:
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
class ActivationWindow(QtWidgets.QMainWindow):
    def __init__(self, mw, *args, **kwargs):
        super(ActivationWindow, self).__init__(*args, **kwargs)
        uic.loadUi('resources/_CD_GUI_ActivationMVC_Formed_Clinician.ui',
                   self)  # load ui from Qt Designer

        #### Initialize Variables ####
        self.mw2 = mw
        self.showMaximized()
        self.time_start = time.time()
        self.pyqtTimerTime = [0]
        self.window_time_start_idx = len(self.mw2.threadX) #index of first point in threadX so export everything after this for just this Window

        #### Setup GUI Widgets ####
        # Connect push buttons and spinners
        self.target_cb.toggled.connect(self.update_target)
        self.download_pb.clicked.connect(self.download)
        self.returnToMain_pb.clicked.connect(self.download)
        self.returnToMain_pb.clicked.connect(self.connect_to_main)
        self.nextPDRamp_pb.clicked.connect(self.download)
        self.nextPDRamp_pb.clicked.connect(self.connect_to_PDRamp)
        self.maxTorqueReset_pb.clicked.connect(self.reset_torque_lcd)

        #### Setup PYQTGRAPH ####
        # Preassign data
        # self.x = list(range(SAMPLES))
        self.x = [0] * SAMPLES
        self.y = [0] * SAMPLES
        self.x_storage = [0]
        self.y_storage = [0]

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
        temp_x = self.mw2.threadX[-1]
        temp_y = self.mw2.threadY[-1]
        
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

    def add_data(self, data_buffer, new_data):
        """Store new data in buffer."""
        data_buffer = data_buffer[1:]
        data_buffer.append(float(new_data))
        return data_buffer

    def reset_torque_lcd(self):
        """Reset max torque lcd to 0"""
        self.max_torque_reached = 0.0
        self.maxTorque_lcd.display(0.0)

    #### MISCELLANEOUS METHODS ####
    def connect_to_main(self):
        """Connect to main GUI."""
        self.mw2.activation_MVC = max(self.mw2.threadY[self.window_time_start_idx:])
        self.mw2.windowFlag = 0
        self.mw2.show()
        self.close()

    def connect_to_PDRamp(self):
        """Connect to main GUI."""
        self.mw2.activation_MVC = max(self.mw2.threadY[self.window_time_start_idx:])
        self.mw2.windowFlag = 2
        self.w4 = RampWindow(self)
        self.close()
        self.w4.show()

    def download(self):
        self.timer.stop()
        """Download data from GUI."""
        default_filename = 'data/' + 'Central_Drive_' + self.mw2.participantID_lbl.text() + '_' + str(self.mw2.currentDate.strftime("%Y%m%d")) + '_ActivationMVC'
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save data file", default_filename, "CSV Files (*.csv)")
        if filename:
            # data_to_save = list(itertools.zip_longest(self.mw2.threadX, self.mw2.threadY, self.x_storage, self.y_storage, self.pyqtTimerTime, self.mw2.windowFlagList))
            time_ = list(np.array(self.mw2.threadX[self.window_time_start_idx:])  - self.mw2.threadX[self.window_time_start_idx]) #reset time to be zero 
            torque_ = self.mw2.threadY[self.window_time_start_idx:]
            window_ = self.mw2.windowFlagList[self.window_time_start_idx:]
            data_to_save = list(itertools.zip_longest(time_, torque_ , window_))
            #create headers for file
            # header6 = "Thread Time (s), Thread Voltage (V), GUI Time (s), GUI Voltage (V), Inner Loop Time (s), Window Flag"
            header1 = "Time (s), Torque (ft-lbs), Window Flag"
            #save data to file
            np.savetxt(filename, data_to_save, delimiter=',', fmt='%s', comments = '', 
                header = '\n'.join([header1]))
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


# Plotting PD Ramp Data:
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
class Ramp_Visualization(QtWidgets.QMainWindow):
    def __init__(self, mw, *args, **kwargs):
        super(Ramp_Visualization, self).__init__(*args, **kwargs)
        uic.loadUi('resources/_CD_GUI_PDRamp_Visualization_Formed_Clinician.ui',
                   self)  # load ui from Qt Designer

        #### Initialize Variables ####
        self.mw2 = mw.mw2

        #### Setup GUI Widgets ####
        # Connect push buttons and spinners
        self.returnToMain_pb.clicked.connect(self.connect_to_main)
        self.nextCDTest_pb.clicked.connect(self.connect_to_CDTest)

        #### Setup PYQTGRAPH ####
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
        pen2 = pg.mkPen(color=([0,0,0]), width=2.5)
        try:
            self.graphWidget.plot(self.mw2.ramptime, self.mw2.rampfes, pen=pen2, name="FES")
            self.graphWidget.plot(self.mw2.ramptime, self.mw2.ramptor, pen=pen1, name="Torque Sensor")
        except:
            pass

    #### MISCELLANEOUS METHODS ####
    def connect_to_main(self):
        """Connect to main GUI."""
        self.mw2.activation_MVC = max(self.mw2.threadY[self.window_time_start_idx:])
        self.mw2.windowFlag = 0
        self.mw2.show()
        self.close()

    def connect_to_CDTest(self):
        """Connect to main GUI."""
        self.mw2.chosenDuration = self.desiredDuration_sp.value()
        self.w3 = CDWindow(self)
        self.windowFlag = 3
        self.close()
        self.w3.show()

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
                y = float((myADC.voltage*-95.64) + 113.3 + 2) #multiply by 1.3558 for Nm
            else:
                # do NOT plot data from here!
                x = float(time.time())
                y = float(datetime.now().second + np.sin(x) + 0.1*np.random.random())
            self.newData.emit([x, y])


# SETUP:
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
app = QtWidgets.QApplication(sys.argv) #pass this into each of my classes

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

w = ConnectWindow(myFES, myADC)
w.show()
myFES.close()
sys.exit(app.exec_())
