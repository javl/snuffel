#! /usr/bin/env python

from socketIO_client import SocketIO
import threading, time, json, sys, getopt
import pyshark

SOCKETIO_HOST = 'localhost'
SOCKETIO_PORT = 80

CAPFILE = "/home/dev/captures/wlan1-jasper-en-bovenbuurman-dhcp-mdns.pcapng"

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
        self.com = Communication()
        self.com.start()

    def run(self):
        print "Reading packets from capture file\n"
        capture = pyshark.FileCapture(CAPFILE, lazy=True)
        packet = None
        for next_packet in capture:
            if(packet):
                time_delta = next_packet.sniff_time - packet.sniff_time
                print "Sleeping %f seconds until next packet." % time_delta.total_seconds()
                time.sleep(time_delta.total_seconds())

            packet = next_packet

            print "Packet of size %s" % packet.length

        print "1: URL, 2: Plain text, 3: Image, 0: exit:\n"
        while not self.event.is_set():
            msg = raw_input()
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
        print "Exit"
        exit()

snuffel = Snuffel()
snuffel.start()
