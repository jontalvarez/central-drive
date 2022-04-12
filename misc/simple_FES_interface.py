from dkc_rehamovelib import *          # Import our library
import time

## CHANGE COM PORT BASED OFF OF DEVICE MANAGER
COM_PORT = "COM6"
r = Rehamove_DKC(COM_PORT)            # Open USB port (on Windows)

##MODIFY THESE PARAMETERS##
amp = 150 #mA
dur = 500 #us
f = 100 #Hz
n_pulse = 10
channelNum = 2 # for channels: 1 = red, 2 = blue, 3 = black, 4 = white
####

r.connect()
r.initialize()

for i in range(0,n_pulse):
   # r.write_pulse(channelNum, [(dur,amp), (50, 0), (dur, -amp)])     # Send pulse every second
   # time.sleep(1.0/f)

   # #Monophasic
   # r.write_pulse(channelNum, [(dur, amp)])     # Send pulse every second
   # time.sleep(1.0/f - dur)

   #Biphasic
   r.write_pulse(channelNum, [(int((dur-50)/2),amp), (50, 0), (int((dur-50)/2), -amp)])     # Send pulse every second
   time.sleep(1.0/f - (dur*(10**-6)))

time.sleep(1)
r.close()