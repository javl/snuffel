#! /usr/bin/env python

from socketIO_client import SocketIO
import argparse, threading, time, json, sys, pyshark, os.path

# Is this something that has to go in the arguments list for commandline control?
DELAY_PACKETS = False 


image_file_extentions = ['.jpg', '.jpeg', '.gif', '.png', '.bmp', '.JPG', '.JPEG', '.GIF', '.PNG', '.BMP']
ignore_extentions = ['.xml', '.js', '.css']
urls_used = []

#======================================================
# Command line argument parsing
#======================================================
parser = argparse.ArgumentParser(prog='Snuffel', description='Finds unencrypted data in your network traffic and sends this data to the Snuffel web interface using Socket.io.',
epilog='''** This program sniffs your network traffic and will try to display as much personal info as possible: use at your own risk **''')
parser.add_argument('-i', default='wlan0', dest="interface", metavar='interface', action='store', help="Set internet interface to use. Defaults to <wlan0>")
parser.add_argument('-f', metavar='filepath', dest="capfile", action='store', help='Use a pre-recorded pcap file, instead of live capturing')
parser.add_argument('-sh', default='localhost', dest="socketio_host", metavar='host', action='store', help="Socket.io host. Defaults to <localhost>")
parser.add_argument('-sp', default=80, type=int, dest="socketio_port", metavar='port', action='store', help="Socket.io port. Defaults to <80>")
parser.add_argument('-v', dest="verbose", action='store_true', help="Verbose mode: show extra output while running")
parser.add_argument('--version', action='version', version='%(prog)s version 0.1')
args = parser.parse_args()

#======================================================
# Handles the socket.io connection in a seperate
# thread, so not to block the main one
#======================================================
class Communication(threading.Thread):

    def __init__(self, host=args.socketio_host, port=args.socketio_port):
        threading.Thread.__init__(self)
        self.event = threading.Event()
        self.setDaemon(True) # so thread doesn't block when Snuffel() calls exit()
        self.host = host
        self.port = port

    def inputCmdReceived(self, *args):
        if args.verbose: print 'Incoming command: {}'.format(args[0]['cmd'])
    
    # sendMsg example:
    #self.com.sendMsg(time.strftime("%H:%M:%S"), 'url', 'http://www.example.com')
    def sendMsg(self, timestamp, msgType, msg):
    	try:
	    	self.socketIO.emit('newMsg', {'timestamp': timestamp, 'msgType': msgType, 'msg': msg})
        except Exception:
        	print "Couldn't send msg to frontend: no Socket.io connection?"

    def run(self):
        if args.verbose: print 'Connecting to Socket.io on {}:{}'.format(self.host, self.port)
        try:
        	self.socketIO = SocketIO(self.host, self.port)
        	self.socketIO.on('inputCmd', self.inputCmdReceived)
        	self.socketIO.wait()
        except Exception:
        	if args.verbose: print "Couldn't connect to Socket.io"

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
    	#check if capfile given and accessible, otherwise fall back to live capture
    	if args.capfile != None:
        	try:
	        	with open(args.capfile):
					if args.verbose: print "Using file: '%s'", args.capfile
                	capsource = pyshark.FileCapture(args.capfile, lazy=True)
        	except IOError:
				if args.verbose:
					print "Couldn't find or open the pcap file '%s'" % args.capfile
				exit()
        else:
        	if args.verbose: print "Starting capture on interface '%s'" % args.interface
        	capture = pyshark.LiveCapture(interface=args.interface)
        	capsource = capture.sniff_continuously()

        # start capture and processing thread
        self.packetflow = PacketFlow(com=self.com, packetsource=capsource)
        self.packetflow.start()

        while 1:
            1 #keep thread alive.

    def stop(self):
        self.packetflow.stop()
        self.event.set()
        if args.verbose: print "Snuffel thread stopping"

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
                if args.verbose: print "Sleeping %f seconds until next packet." % time_delta.total_seconds()
                time.sleep(time_delta.total_seconds())

            packet = next_packet
            # maybe add multiple levels of verbose for this kind of message?
            #if args.verbose: print next_packet.highest_layer
            if next_packet.highest_layer == 'HTTP':
                target = ''
                try:
                    target = packet.http.location
                except Exception:
                    try:
                        target = packet.http.request_full_uri
                    except Exception:
                        pass;

                # remove possible trailing slash to prevent saving url multiple times
                if target[-1:] == '/': target = target[0:-1]
                print target
                fileName, fileExtension = os.path.splitext(target)

                if target != '' and target not in urls_used:
                    urls_used.append(target)
                    # Check if image or 'something else' (a url to some file)
                    if any(x in target for x in image_file_extentions):
                        self.com.sendMsg(time.strftime("%H:%M:%S"), 'img', target)
                    else:
                        if all(x not in target for x in ignore_extentions):
                            1 # in ignore list so skip, would be cleaner to turn
                            self.com.sendMsg(time.strftime("%H:%M:%S"), 'url', target)


    def stop(self):
        self.event.set()
        if args.verbose: print "PacketFlow thread stopping"

def main():
    snuffel = Snuffel()
    snuffel.start()

if __name__ == "__main__":
    main()