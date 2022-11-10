import binascii


# Example packet data:
example_data = b'\x04\x02\x82\x81\x5A\xA5\x50\x00\x06\x44\xB0\x00\x81\x5A\xA4\x10\x00'
example_packet = b'\xF0\x81\x55\x81\x4E\x81\xD3\x81\xAF\x04\x02\x82\x81\x5A\xA5\x50\x00\x06\x44\xB0\x00\x81\x5A\xA4\x10\x00\x0F'

def compute_crc_and_stuff(stuffed_data):
    # CRC data known as length 4 byte
    stuffed_array = bytearray(4)
    crc_int = binascii.crc_hqx(stuffed_data,0)
    crc_array = crc_int.to_bytes(2,'big')

    stuffed_array[0] = 0x81
    stuffed_array[2] = 0x81

    stuffed_array[1] = crc_array[0]^0x55
    stuffed_array[3] = crc_array[1]^0x55

    return stuffed_array

def compute_pktlen_and_stuff(stuffed_data):
    # Len data known as length 4 byte
    stuffed_array = bytearray(4)
    pkt_length = len(stuffed_data) + 10 # including start/stop/length/checksum
    len_array = pkt_length.to_bytes(2,'big')

    stuffed_array[0] = 0x81
    stuffed_array[2] = 0x81

    stuffed_array[1] = len_array[0]^0x55
    stuffed_array[3] = len_array[1]^0x55

    return stuffed_array

def compute_channel_bit(active, channel_number, num_pts):
    act = active << 7 # 1st out of 8 bits is active f'{6:08b}'? 
    chan = (channel_number - 1) << 5 # bit 2,3 are channel (0 index), bit 4 is reserved
    num_points = (num_pts - 1) # last 4 bits are number points = 1pt -> 0, 2 points ->1 etc 

    channel_bit =(act | chan | num_points)
    return channel_bit.to_bytes(1,'big')


def compute_point(dur, amp):
    compute_curr = lambda curr: 2*curr + 300
    bin_dur = dur << 20
    bin_amp = compute_curr(amp) << 10

    return (bin_dur | bin_amp).to_bytes(4,'big')

def generate_point_packet(active, channel, point_list):
    # point list of form [(dur_1, amp_1), (dur_2, amp_2), ...etc ]
    point_pkt = bytearray()

    #Check if # points <= 16 
    n_points = len(point_list)
    if n_points > 16:
        print("warning- number of points exceeds 16, taking first 16")
        n_points = 16

    # Add in channel bit
    chan_bit = compute_channel_bit(active, channel, n_points)
    point_pkt += bytearray(chan_bit)

    for point_tuple in point_list:
        point = compute_point(point_tuple[0], point_tuple[1])
        point_pkt += bytearray(point)

    return point_pkt

def stuff_pkt_data(raw_data):
    stuffed_data = bytearray()
    for byte in raw_data:
        if not (byte^0x81) or not(byte^0x0F) or not(byte^0xF0):
            stuffed_data.append(0x81)
            stuffed_data.append(0x55^byte)
        else:
            stuffed_data.append(byte)

    return stuffed_data


def generate_packet(pkt_num, command_num, active, channel, point_list):
    #Generate stuffed packet from points
    stuffed_command_data = stuff_pkt_data(generate_point_packet(active, channel, point_list))

    #Generate command packets
    command_pkt = ((pkt_num << 10) | (command_num)).to_bytes(2,'big')

    #Compute Length
    length = compute_pktlen_and_stuff(command_pkt+stuffed_command_data)

    #Compute CRC
    crc = compute_crc_and_stuff(command_pkt+stuffed_command_data)

    # Fill in packet
    complete_pkt = bytearray(b'\xF0') + length + crc + command_pkt + stuffed_command_data + bytearray(b'\x0F')

    return complete_pkt


# Example: Test generated from points
# points = [(250,20), (100, 0), (250, -20)]

# # Combine packet
# combined_test_pkt = generate_packet(1, 2, 1, 1, points)
# print (combined_test_pkt.hex())
# print (example_packet.hex())


# print(example_packet == combined_test_pkt)