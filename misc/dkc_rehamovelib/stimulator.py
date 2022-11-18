#from rehamove import *
from DKC_rehamovelib import *
import threading
import time
from PySide.QtCore import *
from PySide.QtGui import *
import serial
import serial.tools.list_ports
from protocol import *

class Stimulator(QObject):
    found_device = Signal(str,str,str)
    connected = Signal(int)

    def __init__(self, port):
        QObject.__init__(self)
        if port != None:
            self.dev = Rehamove_DKC(port)
            
            self.dev.connect() #DKC lib only
            self.dev.initialize() #DKC lib only
        else:
            self.dev = None        
        
        self.channels = [StimChannel(0), StimChannel(1), StimChannel(2), StimChannel(3)]
        
        # Serial connection stuff
        self.port_open = 0
        self.addr = 0 
        self.list_of_serial_port =  serial.tools.list_ports.comports()
        
        
        #for timing
        self.period = 0.002 #ms
        self.i = 0
        self.t0 = time.time()

        # Initialize messages 
        for chan_idx in range(4):
            self.build_CFT_pulse(chan_idx)
            self.build_VFT_pulse(chan_idx)
    
    def build_points_array(self,point_arr, amp, dur):
        #point_arr.append((amp, dur)) # amp and dur for rehalib 
        point_arr.append((dur, amp)) # Dur/amp for dkc_rehalib
        return point_arr

    def build_pulse(self, p0_dur, p0_amp, p1_dur, p1_amp, p2_dur, p2_amp):
        points = []
        self.build_points_array(points, p0_amp, p0_dur)
        self.build_points_array(points, p1_amp, p1_dur)
        self.build_points_array(points, p2_amp, p2_dur)
        return points

    def build_triple_pulse(self, vft_freq, p0_dur, p0_amp, p1_dur, p1_amp, p2_dur, p2_amp):
        points = []
        filler_time = ((1000000/vft_freq) - p0_dur - p1_dur - p2_dur)/2

        for i in range(3):
            self.build_points_array(points, p0_amp, p0_dur)
            self.build_points_array(points, p1_amp, p1_dur)
            self.build_points_array(points, p2_amp, p2_dur)
            self.build_points_array(points, 0, filler_time)
            self.build_points_array(points, 0, filler_time)
        
        return points

    def build_VFT_pulse(self,channel_idx):
        dur = self.channels[channel_idx].dur
        pause = self.channels[channel_idx].pause
        amp = self.channels[channel_idx].amp

        self.channels[channel_idx].message_VFT = self.build_triple_pulse(self.channels[channel_idx].VFT_freq, dur, amp, pause, 0, dur, -amp)
        return 0

    def build_CFT_pulse(self,channel_idx):
        dur = self.channels[channel_idx].dur
        pause = self.channels[channel_idx].pause
        amp = self.channels[channel_idx].amp

        self.channels[channel_idx].message_CFT = self.build_pulse(dur, amp, pause, 0, dur, -amp)
        return 0

    def update_channel_config(self, channel_idx):
        self.build_CFT_pulse(channel_idx)
        self.build_VFT_pulse(channel_idx)
        return 0


    def rebuild_stimulator_signals(self):
        # print("REBUILDING STIMULATOR MESSAGE")
        for i in range(4): # UPDATE UP TO 4
            self.update_channel_config(i)
        return 0

    def channel_update(self, channel_idx,t_ms):
        vft_flag = False
        time_start = time.time()
        if self.channels[channel_idx].active and not self.channels[channel_idx].prev_active:
            self.channels[channel_idx].t_pulse_start = t_ms # replace with current time

            if self.channels[channel_idx].VFT: 
                vft_flag = True 
        
        if self.channels[channel_idx].active and ((t_ms - self.channels[channel_idx].t_last_pulse) >= self.channels[channel_idx].pulse_period_ms) and ((t_ms - self.channels[channel_idx].t_pulse_start) < 50000): # 20000 ms = 20 s max pulse duration //hardcoded
            if self.channels[channel_idx].VFT:
                #print ("CHANNEL {0}: PRE-STIM: {1}".format(channel_idx,time.time()-time_start))
                self.dev.write_pulse(self.channels[channel_idx].id, self.channels[channel_idx].message_VFT)
                #print ("CHANNEL {0}: POST-STIM: {1}".format(channel_idx,time.time()-time_start))
            else:
                self.dev.write_pulse(self.channels[channel_idx].id, self.channels[channel_idx].message_CFT)
            self.channels[channel_idx].t_last_pulse = t_ms
        
        self.channels[channel_idx].prev_active = self.channels[channel_idx].active
        # print ("CHANNEL {0}: Total Time elapsed: {1}\n".format(channel_idx,time.time()-time_start))
    
    def hasomed_update(self,t_ms):
        #print("current time: {0}\n".format(t_ms-self.time_start))
        self.channel_update(0,t_ms)
        self.channel_update(1,t_ms)
        self.channel_update(2,t_ms)
        self.channel_update(3,t_ms)

    
    def enumerate_device(self):
        self.list_of_serial_port = serial.tools.list_ports.comports()
        for device in self.list_of_serial_port:
           self.found_device.emit(device[0],device[1],device[2])

    def select_device(self,name):
        self.addr = name

    def connect_stimulator(self):
        self.port_open = 1
        self.connected.emit(1)
    
    def is_connected(self): 
        return self.port_open

    def disconnect(self):
        self.port_open = 0 
        self.connected.emit(0)
        if self.dev != None: 
            self.dev.close()
            
    def sleep(self):
       self.i +=1
       delta = self.t0 + self.period * self.i - time.time()
       if delta>0:
           time.sleep(delta)
  
    def disable_stim(self):
        for i in range(4):
            self.channels[i].set_active(0)

    def set_stim_enable(self,chan_idx,act_flag):
        self.channels[chan_idx].set_active(act_flag)
        self.update_channel_config(chan_idx)

    def set_stim_amp(self,chan_idx, amp):
        self.channels[chan_idx].set_amp(amp)
        self.update_channel_config(chan_idx)
    
    def set_stim_dur(self,chan_idx, dur):
        self.channels[chan_idx].set_dur(dur)
        self.update_channel_config(chan_idx)

    def get_stim_amp(self,chan_idx):
        return self.channels[chan_idx].get_amp()
    
    def get_stim_dur(self,chan_idx):
        return self.channels[chan_idx].get_dur()
        


class StimChannel:
    def __init__(self,id):
        self.id = id

        # General Pulse parameters
        self.amp = 0
        self.dur = 400
        # settings for CFT
        self.CFT_freq = 30
        self.pulse_period_ms = 1000/self.CFT_freq


        # settings for VFT
        self.VFT = 1
        self.VFT_freq = 200

        

        # Channel configuration
        self.active = 0
        self.prev_active = 0

        self.t_last_pulse = 0
        self.t_pulse_start = 0 
        self.pause = 50 # in us -> not sure why this is here? to space out pulses

        self.message_VFT = []
        self.message_CFT = []
        
        self.set_attr_dict = {"VFT": self.set_VFT ,"CFT_freq":self.set_freq,"amp":self.set_amp,"dur": self.set_dur,"active":self.set_active}
        self.get_attr_dict = {"VFT": self.get_VFT ,"CFT_freq":self.get_freq,"amp":self.get_amp,"dur": self.get_dur,"active":self.get_active}

    # Getters
    def get_freq(self):
        return self.CFT_freq
    
    def get_active(self):
        return self.active
    
    def get_amp(self):
        return self.amp
    
    def get_dur(self):
        return self.dur

    def get_VFT(self):
        return self.VFT
        

    # Setters
    def set_VFT(self,val):
        self.VFT = val
        return 0

    def set_active(self,val):
        self.active = val
        return 0

    def set_amp(self,val):
        self.amp = val
        return 0

    def set_dur(self,val):
        self.dur = val
        return 0
    
    def set_freq(self,val):
        self.CFT_freq = val
        self.pulse_period_ms = 1000/self.CFT_freq
        return 0

    
    def dispatch(self, id, val, get_flag):
        if get_flag == 0: 
            ret_val = self.get_attr_dict[id]()
        else:
            ret_val = self.set_attr_dict[id](val)
        return ret_val
        

 
