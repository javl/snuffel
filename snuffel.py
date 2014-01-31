#! /usr/bin/env python

from socketIO_client import SocketIO
import threading, time, json


#======================================================
# Handles the socket.io connection in a seperate
# thread, so not to block the main one
#======================================================
class Communication(threading.Thread):

    def __init__(self, host='localhost', port=80):
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