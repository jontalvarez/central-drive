from dkc_rehamovelib.DKC_rehamovelib import *  # Import our library
import time

## CHANGE COM PORT BASED OFF OF DEVICE MANAGER
COM_PORT = "COM6"
r = Rehamove_DKC(COM_PORT)            # Open USB port (on Windows)
# s = Stimulator(COM_PORT)

# s.build_CFT_pulse
# s.hasomed_uppdate

##MODIFY THESE PARAMETERS## %test with 10 mA, 500 us, 1 Hz, 2 pulses on forearm to check if it works
amp = 90 #mA
dur = 50 #us
f = 100 #Hz
n_pulse = 5 #15 normally
channelNum = 2 # for channels: 1 = red, 2 = blue, 3 = black, 4 = white
###

r.connect()
r.initialize()

# r.write_pulse(channelNum, [(50, 10), (0,0), (50, -10), (9950, 0)])#, (9950, 0), (9950, 0), (50, 10), (0, 0), (50, -10), (9950, 0), (9950, 0)])     # Send pulse every second

# r.set_amp(amp) #setter functions
# r.set_dur(dur)
# r.set_freq(f)
# r.build_CD_pulse()
# print(r.message_CD)
# r.write_pulse(channelNum, r.message_CD)
# r.write_pulse(channelNum, r.message_CD)
# r.write_pulse(channelNum, r.message_CD)
# r.write_pulse(channelNum, r.message_CD)
# r.write_pulse(channelNum, r.message_CD)

# for i in range(0,n_pulse):
#    # print(dur)
#    #Biphasic
#    r.write_pulse(channelNum, [(int((dur)/2),amp), (int((dur)/2), -amp)])     # Send pulse every second
#    time.sleep(1.0/f - (dur*(10**-6)))

# while dur <= 600:
#    for i in range(0,n_pulse):
#       print(dur)
#       #Biphasic
#       r.write_pulse(channelNum, [(int((dur)/2),amp), (int((dur)/2), -amp)])     # Send pulse every second
#       # time.sleep(1.0/f - (dur*(10**-6)))
#       time.sleep(3)
#    dur = dur + 50

while dur <= 300:
   for i in range(0,n_pulse):
      #Biphasic
      r.write_pulse(channelNum, [(int((dur)/2),amp), (int((dur)/2), -amp)])     # Send pulse every second
      time.sleep(1.0/f - (dur*(10**-6)))
   time.sleep(3)
   dur = dur + 25
   print(dur)

time.sleep(1)
r.close()