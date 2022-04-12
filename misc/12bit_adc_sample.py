import board
import busio
import time
import numpy as np
import matplotlib.pyplot as plt
i2c = busio.I2C(board.SCL, board.SDA)

import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
ads = ADS.ADS1115(i2c)
ads.data_rate = 860

# Create single-ended input on channel 0
chan = AnalogIn(ads, ADS.P0)

print("Starting now...")
print("Press Ctrl+C to end.")
max_voltage_seen = 5.0
x = [0]
try:
    while True:
        if chan.voltage < max_voltage_seen:
            max_voltage_seen = chan.voltage
        x.append(chan.voltage)

except KeyboardInterrupt:
    #np.savetxt("calibration/80_2.csv", x[1:], delimiter=",")
    print(np.min(x[1:]))
    plt.plot(x[1:])
    plt.show()
    #print("{:>5}\t{:>5.3f}\t{:>5.3f}".format(chan.value, chan.voltage, max_voltage_seen))
    #time.sleep(0.01)

