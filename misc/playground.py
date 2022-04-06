import pyqtgraph as pg
import numpy as np
from pyqtgraph.Qt import QtCore, QtGui
import random
import sys
import sys


import pyqtgraph as pg
import time

plt = pg.plot()

def update(data):
    plt.plot(data, clear=True)

class Thread(pg.QtCore.QThread):
    newData = pg.QtCore.Signal(object)
    def run(self):
        while True:
            data = np.random.normal(size=100)

            # do NOT plot data from here!

            self.newData.emit(data)
            time.sleep(0.05)

thread = Thread()
thread.newData.connect(update)
thread.start()


# timer = pg.QtCore.QTimer()
# timer.timeout.connect(update)
# timer.start(0) #Hopefully makes it run as fast as possible.


if __name__ == '__main__':
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
