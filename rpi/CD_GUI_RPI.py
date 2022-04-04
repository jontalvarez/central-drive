from PyQt5 import QtWidgets, QtCore, uic
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from pyqtgraph import PlotWidget, plot
import pyqtgraph as pg
import sys  
import numpy as np
import serial.tools.list_ports; 
import os
import time
from dkc_rehamovelib.DKC_rehamovelib import * # Import our library
from datetime import datetime
import busio
import digitalio
import board
# import adafruit_mcp3xxx.mcp3008 as MCP
# from adafruit_mcp3xxx.analog_in import AnalogIn


import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn


SAMPLES = 1000
SAMPLES_ = 100
DATA_NB = 1

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
## WINDOW: LANDING PAGE
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------

class Window1(QDialog):
	def __init__(self, myFES, *args, **kwargs):
		super().__init__(*args, **kwargs)
		uic.loadUi('resources/_CD_GUI_Landing_Formed.ui', self)

		#find existing COM Ports
		self.comports = serial.tools.list_ports.comports(include_links=True)
		for comport in self.comports:
			self.portSelect_cb.addItem(comport.description)

		self.startPlotting_pb.clicked.connect(self.connect_to_main) 

	def key_press_event(self, e):
		if e.key() == Qt.Key_Escape:
			self.close()

	def connect_to_main(self):
		self.w2 = Window2(myFES, myADC)
		self.w2.comport_le.setText(self.comports[self.portSelect_cb.currentIndex()].device)
		# print(str(self.comports[self.portSelect_cb.currentIndex()].device))
		# myFES = Rehamove_DKC(str(self.comports[self.portSelect_cb.currentIndex()].device)); # Open USB port (on Windows) -- maybe will want a dropdown		
		# self.w2.FES.write_pulse(2, [(150,  10), (50, 0), (150, -10)])
# 		myFES.port = str(self.comports[self.portSelect_cb.currentIndex()].device)
		myFES.port = "/dev/ttyUSB0"
		myFES.connect()
		myFES.initialize()
		if myFES.is_connected():
			# self.connect_lbl.setText('Successful')
			# self.connect_lbl.setStyleSheet('color: Green')
			# time.sleep(1)
			self.w2.show()
			self.close()
		else:
			self.connect_lbl.setText('Unsuccessful')
			self.connect_lbl.setStyleSheet('color: red')

## MAIN WINDOW:
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------------
# https://www.youtube.com/watch?v=XXPNpdaK9WA
class Window2(QtWidgets.QMainWindow):
	def __init__(self, myFES, myADC, *args, **kwargs):
		super(Window2, self).__init__(*args, **kwargs)
		uic.loadUi('resources/_CD_GUI_Main_Formed.ui', self) # load ui from Qt Designer
		#connect push buttons and spinners
		self.time_start = time.time()
		
		self.channel_cb.addItems([' ', '1 (Red)', '2 (Blue)', '3 (Black)', '4 (White)'])
		self.amp_sp.setRange(0, 50)
		self.dur_sp.setRange(0, 500)
		self.f_sp.setRange(0, 10)
		self.np_sp.setRange(0, 100)
		self.max_value_reached = 0

		self.amp_sp.setValue(15)
		self.dur_sp.setValue(150)
		self.f_sp.setValue(1)
		self.np_sp.setValue(1)

		self.commit_pb.clicked.connect(self.update_lcd)

		self.target_cb.toggled.connect(self.update_target)
		self.download_pb.clicked.connect(self.download)
		self.sendPulse_pb.clicked.connect(self.update_fes)
		self.CD_pb.clicked.connect(self.connect_to_Window3)

		#prepare scrolling graph from pyqtgraph
		self.graphWidget = pg.PlotWidget()
		self.findChild(QWidget, "TorquePlot").layout().addWidget(self.graphWidget)

		self.x = list(range(SAMPLES)) 
		self.y1 = [0] * SAMPLES  
		self.x_storage = []
		self.y1_storage = []

		self.graphWidget.setBackground('w')
		self.graphWidget.setTitle("Central Drive Estimation")
		self.graphWidget.setLabel('left', 'Torque (ft-lbs)')
		self.graphWidget.setLabel('bottom', 'Samples')
		self.graphWidget.showGrid(x=False, y=True)
		# self.graphWidget.setYRange(0, 10, padding=1)
		self.graphWidget.enableAutoRange('y', 0.95)
		self.graphWidget.addLegend()
		pen_ref = pg.mkPen(color=(192,192,192), width=1, style=QtCore.Qt.DashLine)

		pen1 = pg.mkPen(color=(0,123,184), width=2)

		self.data_line1 = self.graphWidget.plot(self.x, self.y1, pen=pen1, name="Torque Sensor")

		self.timer = QtCore.QTimer()
		self.timer.setInterval(10)
		self.timer.timeout.connect(self.update_gui)
		self.timer.start()

		# Setup a PAUSE button in a toolbar
		self.toolbar = self.addToolBar("Pause")
		self.pause_tb = QAction("Pause", self)
		self.pause_tb.triggered.connect(self.pause_plotting)
		self.pause_tb.setCheckable(True)
		self.toolbar.addAction(self.pause_tb)

	def pause_plotting(self):
		if self.pause_tb.isChecked():
			self.timer.stop()
		else:
			self.timer.start()

	def update_lcd(self):
		self.committedAmp_lbl.display(self.amp_sp.value())
		self.committedDur_lbl.display(self.dur_sp.value())
		self.committedF_lbl.display(self.f_sp.value())
# 		self.committedNp_lbl.display(self.np_sp.value())

	def update_target(self):
		if self.target_cb.isChecked():
			self.target = pg.InfiniteLine(movable=True, angle=0, pen = {'color': 'r', 'width': 10}, label='Torque Target ={value:0.2f}', 
                       labelOpts={'position':0.5, 'color': (200,0,0), 'fill': (200,200,200,50), 'movable': True})
			self.graphWidget.addItem(self.target)
		else:
			self.graphWidget.removeItem(self.target)
			
	def update_gui(self):
		self.update_plot()

	def update_plot(self):
		self.x = self.add_data(self.x, time.time()-self.time_start)
		self.y1 = self.add_data(self.y1, (myADC.voltage))
		
		self.x_storage.append(float(time.time()-self.time_start)))
		self.y1_storage.append(float(myADC.voltage))
		self.data_line1.setData(self.x, self.y1)
		if (float(myADC.voltage) > self.max_value_reached):
			self.max_value_reached = (float(myADC.voltage))
			self.committedNp_lbl.display(self.max_value_reached)


	def add_data(self, data_buffer, new_data): # append new data to buffer
		data_buffer = data_buffer[1:]
		data_buffer.append(float(new_data))
		return data_buffer

	def key_press_event(self, event):
		if event.key() == Qt.Key_Escape:
			self.close()

	def connect_to_Window3(self):
		self.w3 = Window3(self)
		self.close()
		self.w3.show()

	def download(self):
		default_filename = 'CD_' + datetime.now().strftime("%Y%m%d-%H%M%S")
		filename, _ = QFileDialog.getSaveFileName(self, "Save data file", default_filename, "CSV Files (*.csv)")
		if filename:
			data_to_save = list(zip(self.x_storage, self.y1_storage))
			np.savetxt(filename + '.csv', data_to_save, delimiter = ',')
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Information)
			msg.setText("Download completed successfully!")
			msg.setWindowTitle("Success")
			msg.exec()

	def update_fes(self): #, amp):
		# self.commitedAmp_lbl.display(self.amp_sp.value())
		if self.fesEnable_cb.isChecked():
			self.test_fes()
		else:
			pass

	def test_fes(self):
		amp = int(self.committedAmp_lbl.value()) # [mA]
		dur = int(self.committedDur_lbl.value()) # [us]
		f = int(self.committedF_lbl.value()) # hz
		n_pulse = int(self.committedNp_lbl.value())

		try:
			channelNum = int(self.channel_cb.currentText()[0]) # for channels: 1 = red, 2 = blue, 3 = black, 4 = white
			self.send_pulse_fes(amp, dur, f, n_pulse, channelNum)
		except:
			print('No Channel Selected')

	def send_pulse_fes(self, amp, dur, f, n_pulse, channelNum):
		for i in range(0,n_pulse):
			if f == 1:
				myFES.write_pulse(channelNum, [(dur,amp), (50, 0), (dur, -amp)])     # Send pulse every second
				print('Hasomed Pulse Sent')
			else:
				myFES.write_pulse(channelNum, [(dur,amp), (50, 0), (dur, -amp)])     # Send pulse every second
				print('Hasomed Pulse Sent')
				time.sleep(1.0/f)		

	# def closeEvent(self, event):
	# 	reply = QMessageBox.question(self, 'Window Close', 'Are you sure you want to close the window?',
	# 			QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

	# 	if reply == QMessageBox.Yes:
	# 		event.accept()
	# 		self.FES.disconnect()
	# 	else:
	# 		event.ignore()

class Window3(QtWidgets.QMainWindow):
	def __init__(self, w2, *args, **kwargs):
		super(Window3, self).__init__(*args, **kwargs)
		uic.loadUi('resources/_CD_GUI_CDTest_Formed.ui', self) # load ui from Qt Designer

		self.w22 = w2
		self.test_complete = False

		self.time_start = time.time()
		#grab values commited to Hasomed Device from Window2
		self.channel_lbl.setText(self.w22.channel_cb.currentText()) 
		self.committedAmp_lbl.display(self.w22.committedAmp_lbl.value()) 
		self.committedDur_lbl.display(self.w22.committedDur_lbl.value())
		self.committedF_lbl.display(self.w22.committedF_lbl.value())
		self.committedNp_lbl.display(self.w22.committedNp_lbl.value())

		#connect push buttons and spinners
		self.target_cb.toggled.connect(self.update_target)
		self.download_pb.clicked.connect(self.download)
		self.returnToMain_pb.clicked.connect(self.connect_to_main)


		self.x = list(range(SAMPLES)) 
		self.y1 = [0] * SAMPLES
		self.x_storage = []
		self.y1_storage = []

		#prepare scrolling graph from pyqtgraph
		self.graphWidget = pg.PlotWidget()
		self.findChild(QWidget, "TorquePlot").layout().addWidget(self.graphWidget)

		self.graphWidget.setBackground('w')
		self.graphWidget.setTitle("Central Drive Estimation")
		self.graphWidget.setLabel('left', 'Torque (ft-lbs)')
		self.graphWidget.setLabel('bottom', 'Samples')
		self.graphWidget.showGrid(x=False, y=True)
		# self.graphWidget.setYRange(0, 10, padding=1)
		self.graphWidget.enableAutoRange('y', 0.95)
		self.graphWidget.addLegend()		

		pen_ref = pg.mkPen(color=(192,192,192), width=1, style=QtCore.Qt.DashLine)

		pen1 = pg.mkPen(color=(0,123,184), width=2)

		self.data_line1 = self.graphWidget.plot(self.x, self.y1, pen=pen1, name="Torque Sensor")

		#Don't beging plotting until threshold is met 
		# print(self.y1[-1])
		# if self.y1[-1] < 2:
		# 	print('here')
		# else:
		# 	print('this is not working')

		self.timer = QtCore.QTimer()
		self.timer.setInterval(1)
		self.timer.timeout.connect(self.update_plot)
		self.timer.start()

		# Setup a PAUSE button in a toolbar
		self.toolbar = self.addToolBar("Pause")
		self.pause_tb = QAction("Pause", self)
		self.pause_tb.triggered.connect(self.pause_plotting)
		self.pause_tb.setCheckable(True)
		self.toolbar.addAction(self.pause_tb)

	def pause_plotting(self):
		if self.pause_tb.isChecked():
			self.timer.stop()
		else:
			self.timer.start()

	def update_lcd(self):
		self.amp_lcd.display(self.amp_sp.value())

	def update_target(self):
		if self.target_cb.isChecked():
			self.target = pg.InfiniteLine(movable=True, angle=0, pen = {'color': 'r', 'width': 10}, label='Torque Target ={value:0.2f}', 
                       labelOpts={'position':0.5, 'color': (200,0,0), 'fill': (200,200,200,50), 'movable': True})
			self.graphWidget.addItem(self.target)
		else:
			self.graphWidget.removeItem(self.target)
			
	def update_gui(self):
		self.update_plot()

	def update_vals(self):
		print(self.y1[-1])
		if self.y1[-1] < 2:
			print('here')
			self.timer.stop()
		else:
			print('this is not working')
			self.timer.start()
			
	def update_plot(self):

		self.x = self.add_data(self.x, time.time()-self.time_start))
		self.y1 = self.add_data(self.y1, (myADC.voltage))
		
		self.x_storage.append(float(time.time()-self.time_start)))
		self.y1_storage.append(float(myADC.voltage))
		self.data_line1.setData(self.x, self.y1)
		i = 1

		if not self.test_complete:
			if (myADC.voltage) > 0:
				if int(np.size(self.y1_storage)) > 51:
					if not np.any(np.array(self.y1_storage[-50:]) < 0):
						print('success')
						self.test_complete = True
		# print(self.y1)
		# if self.y1[0] > 4000:
		# 	self.sendPulseFES()

		# if self.y2[0] > 4000:
		# 	self.sendPulseFES()
		self.data_line1.setData(self.x, self.y1)

	def add_data(self, data_buffer, new_data): # append new data to buffer
		data_buffer = data_buffer[1:]
		data_buffer.append(float(new_data))
		return data_buffer

	def key_press_event(self, event):
		if event.key() == Qt.Key_Escape:
			self.close()

	def connect_to_main(self):
		self.w22.show()
		self.close()

	def download(self):
		default_filename = 'CD_' + datetime.now().strftime("%Y%m%d-%H%M%S")
		filename, _ = QFileDialog.getSaveFileName(self, "Save data file", default_filename, "CSV Files (*.csv)")
		if filename:
			data_to_save = list(zip(self.x_storage, self.y1_storage))
			np.savetxt(filename + '.csv', data_to_save, delimiter = ',')
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Information)
			msg.setText("Download completed successfully!")
			msg.setWindowTitle("Success")
			msg.exec()

	def update_fes(self): #, amp):
		# self.commitedAmp_lbl.display(self.amp_sp.value())
		if self.fesEnable_cb.isChecked():
			self.test_fes()
		else:
			pass

	def test_fes(self):
		amp = int(self.committedAmp_lbl.value()) # [mA]
		dur = int(self.committedDur_lbl.value()) # [us]
		f = int(self.committedF_lbl.value()) # hz
		n_pulse = int(self.committedNp_lbl.value())

		try:
			channelNum = int(self.channel_cb.currentText()[0]) # for channels: 1 = red, 2 = blue, 3 = black, 4 = white
			self.send_pulse_fes(amp, dur, f, n_pulse, channelNum)
		except:
			print('No Channel Selected')

	def send_pulse_fes(self, amp, dur, f, n_pulse, channelNum):
		for i in range(0,n_pulse):
			if f == 1:
				myFES.write_pulse(channelNum, [(dur,amp), (50, 0), (dur, -amp)])     # Send pulse every second
				print('Hasomed Pulse Sent')
			else:
				myFES.write_pulse(channelNum, [(dur,amp), (50, 0), (dur, -amp)])     # Send pulse every second
				print('Hasomedd Pulse Sent')
				time.sleep(1.0/f)		

app = QtWidgets.QApplication(sys.argv)

#setup FES
myFES = Rehamove_DKC("None")

#setup ADC
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
# Create single-ended input on channel 0
myADC = AnalogIn(ads, ADS.P0)

w = Window1(myFES)
w.show()
myFES.close()
sys.exit(app.exec_())
