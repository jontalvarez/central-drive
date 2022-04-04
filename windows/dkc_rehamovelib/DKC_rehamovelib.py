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