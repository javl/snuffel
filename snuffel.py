#! /usr/bin/env python

from socketIO_client import SocketIO
import threading, time, json, sys, getopt
import pyshark

SOCKETIO_HOST = 'localhost'
SOCKETIO_PORT = 80

# Capture settings
CAPFILE = "/home/dev/captures/1.pcapng"
CAPINTERFACE = "wlan0"
# Delay handling packets by their sniff time
DELAY_PACKETS = True

DEBUG = True

#======================================================
# Command line argument parsing
#======================================================
try:
    opts, args = getopt.getopt(sys.argv[1:],"p:h:")
except getopt.GetoptError:
    print 'Usage: snuffel.py -h <socketio-host> -p <socketio-port>'
    sys.exit(1)
for opt, arg in opts:
    if opt == '-p' and arg.isdigit():
        SOCKETIO_PORT = int(arg)
    elif opt == '-h':
        SOCKETIO_HOST = arg

#======================================================
# Handles the socket.io connection in a seperate
# thread, so not to block the main one
#======================================================
class Communication(threading.Thread):

    def __init__(self, host=SOCKETIO_HOST, port=SOCKETIO_PORT):
        threading.Thread.__init__(self)
        self.event = threading.Event()
        self.setDaemon(True) # so thread doesn't block when Snuffel() calls exit()
        self.host = host
        self.port = port

    def inputCmdReceived(self, *args):
        print 'Incoming command: {}'.format(args[0]['cmd'])
    
    def sendMsg(self, timestamp, msgType, msg):
        self.socketIO.emit('newMsg', {'timestamp': timestamp, 'msgType': msgType, 'msg': msg})    

    def run(self):
        print 'Connecting to socket.io on {}:{}\n'.format(self.host, self.port)
        self.socketIO = SocketIO(self.host, self.port)
        self.socketIO.on('inputCmd', self.inputCmdReceived)
        self.socketIO.wait()

#======================================================
# The main snuffel thread. At this point only
# responds to keyboard input to for testing purposes
#======================================================
class Snuffel(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.event = threading.Event()

        # communication with the frontend
        self.com = Communication()
        self.com.start()

    def run(self):
        #capture = pyshark.LiveCapture(interface=CAPINTERFACE)
        #capsource = capture.sniff_continuously()
        capsource = pyshark.FileCapture(CAPFILE, lazy=True)

        # start capture and processing thread
        self.packetflow = PacketFlow(com=self.com, packetsource=capsource)
        self.packetflow.start()

        print "1: URL, 2: Plain text, 3: Image, 0: exit:\n"
        while not self.event.is_set():
            msg = raw_input("> ")
            if msg == '0':
                self.stop()
            elif msg == '1':
                print "Sending URL"
                self.com.sendMsg(time.strftime("%H:%M:%S"), 'url', 'http://www.example.com')
            elif msg == '2':
                print "Sending text"
                self.com.sendMsg(time.strftime("%H:%M:%S"), 'txt', 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vestibulum aliquet orci massa, in dapibus sapien vestibulum iaculis. Fusce pharetra, quam vitae vestibulum elementum, leo justo semper dolor, nec viverra nibh erat eu odio.')
            elif msg == '3':
                print "Sending image"
                self.com.sendMsg(time.strftime("%H:%M:%S"), 'img', 'http://placekitten.com/300/300')

    def stop(self):
        self.packetflow.stop()
        self.event.set()
        print "Snuffel thread stopping"

#======================================================
# The packet retrieval and analyzer thread 
#======================================================
class PacketFlow(threading.Thread):

    def __init__(self, com, packetsource, delay_packets=False):
        threading.Thread.__init__(self)
        self.event = threading.Event()
        self.com = com
        self.packetsource = packetsource
        if DELAY_PACKETS:
            self.delay_packets = DELAY_PACKETS
        else:
            self.delay_packets = delay_packets

    def run(self):
        packet = None

        while not self.event.is_set():
            next_packet = self.packetsource.next()
            if self.delay_packets and packet is not None:
                time_delta = next_packet.sniff_time - packet.sniff_time
                if DEBUG:
                    print "Sleeping %f seconds until next packet." % time_delta.total_seconds()
                time.sleep(time_delta.total_seconds())

            packet = next_packet
            if DEBUG:
                print next_packet.highest_layer

    def stop(self):
        self.event.set()
        print "PacketFlow thread stopping"

snuffel = Snuffel()
snuffel.start()
