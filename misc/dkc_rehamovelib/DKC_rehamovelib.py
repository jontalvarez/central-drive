import serial
import struct
import binascii
import time

from threading import Timer
from dkc_rehamovelib.hasomed_packet_generator import *

class Rehamove_DKC:
    def __init__(self, port):
        self.terminator = b'\x0f'
        self.init_packet = bytearray(b'\xf0\x81U\x81X\x81U\x81U\x00\x00\x00\x0f')
        self.port = port
        self.ser = None
        self.port_open = 0
        self.dur = 0
        self.amp = 0
        self.freq = 0
        self.channels = [StimChannel(0), StimChannel(1), StimChannel(2), StimChannel(3)]
        self.message_CD = []

    def connect(self):
        try:
            self.ser = serial.Serial(port=self.port, baudrate=3000000, bytesize=8, parity='N', stopbits=2, timeout=None, xonxoff=False, rtscts=True, write_timeout=None, dsrdtr=False, inter_byte_timeout=None, exclusive=None)
            print('Port {0} Opened'.format(self.port))
            self.port_open = 1
        except:
            print("Error - cannot open Port: {0}".format(self.port))
            self.port_open = 0

    def is_connected(self):
        return self.port_open

    def initialize(self):
        # Initialize Hasomed if port opened
        if self.ser is not None:
            sent = self.ser.write(self.init_packet)
            print (sent)

            response = self.ser.read_until(self.terminator, 100)
            print(binascii.hexlify(response))
        
        else:
            print("Error: Serial communication not enabled")

    def close(self):
        if self.ser is not None:
            print ("Disconnecting Rehamove from port {0}".format(self.port))
            self.ser.close()

    def set_amp(self, amp):
        self.amp = amp

    def set_dur(self, dur):
        self.dur = int(dur)

    def set_freq(self, freq):
        self.freq = freq

    def write_pulse(self, chan, points):
        pkt_num = 1 #Not important but can change to keep track of commands for debugging
        command_num = 2 # channel config command is 2 in LL hasomed protocol
        active = 1 #default to 1 (will switch active)
        pkt = generate_packet(1, command_num, active, chan, points)
        
        if self.ser is not None:
            res = self.ser.write(pkt)
            return res

        else:
            return 0 

#ADDING FROM STIMULATOR CLASS
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

    def build_triple_pulse(self, vft_freq, p0_dur, p0_amp, p1_dur, p1_amp):
        points = []
        filler_time = int(((1000000/vft_freq) - p0_dur - p1_dur)/3)
        print(filler_time)
        for i in range(3):
            self.build_points_array(points, p0_amp, p0_dur)
            self.build_points_array(points, p1_amp, p1_dur)
            self.build_points_array(points, 0, filler_time)
            self.build_points_array(points, 0, filler_time)
            self.build_points_array(points, 0, filler_time)
        return points

    def build_CD_pulse(self):
        pause = 0
        self.message_CD = self.build_triple_pulse(self.freq, self.dur, self.amp, self.dur, -self.amp)
        return 0

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