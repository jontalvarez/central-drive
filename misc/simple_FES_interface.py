from dkc_rehamovelib.DKC_rehamovelib import *  # Import our library
import time

## CHANGE COM PORT BASED OFF OF DEVICE MANAGER
COM_PORT = "COM6"
r = Rehamove_DKC(COM_PORT)            # Open USB port (on Windows)

##MODIFY THESE PARAMETERS## %test with 10 mA, 500 us, 1 Hz, 2 pulses on forearm to check if it works
amp = 150 #mA
dur = 550 #us
f = 100 #Hz
n_pulse = 15 #15 normally
channelNum = 2 # for channels: 1 = red, 2 = blue, 3 = black, 4 = white
####

r.connect()
r.initialize()

for i in range(0,n_pulse):
   print(dur)
   #Biphasic
   r.write_pulse(channelNum, [(int((dur)/2),amp), (int((dur)/2), -amp)])     # Send pulse every second
   time.sleep(1.0/f - (dur*(10**-6)))

# while dur <= 600:
#    for i in range(0,n_pulse):
#       print(dur)
#       #Biphasic
#       r.write_pulse(channelNum, [(int((dur)/2),amp), (int((dur)/2), -amp)])     # Send pulse every second
#       # time.sleep(1.0/f - (dur*(10**-6)))
#       time.sleep(3)
#    dur = dur + 50

time.sleep(1)
r.close()