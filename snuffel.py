#! /usr/bin/env python
"""
Snuffel sniffs your internet traffic to show you what kind
of visible data you're broadcasting to others.
Run ./snuffel.py --help for more info.
"""

#======================================================
# Imports
#======================================================
from flask import Flask, render_template, request

from socketio import socketio_manage
from socketio.namespace import BaseNamespace
from socketio.server import SocketIOServer
from socketio.mixins import BroadcastMixin

import pyshark, threading, time, os, sys, socket, json

# Will be used to easily connect to wifi networks
from wifi import Cell, Scheme

#======================================================
# Parse commandline arguments (before importing
# snuffelControl so it will have access to ARGS)
#======================================================
import argparse
from argparse import RawTextHelpFormatter

PARSER = argparse.ArgumentParser(prog='snuffel',
description='''Snuffel will listen to your network traffic - either on a specified live
interface or from a pre-recorded .pcap file - and will try to find as
much personal info in this traffic as possible. At the same time, Snuffel
runs a webserver to present this info on a website you can access from
a mobile device, like a tablet or smartphone.
 
Snuffel is not a hacking tool. It is meant to create awareness about the
amount of publicly accessible data in your daily internet traffic.

By default, Snuffel creates an accesspoint on wlan0 for the user's computer
to connect to, while at the same time using wlan1 to connect to an existing
wifi network in order to provide internet access.''',
epilog='''*** Do keep in mind that Snuffel will try to show as much info
as possible. Use this at your own risk. ***''',
formatter_class=RawTextHelpFormatter, add_help=False)

PARSER.add_argument('-i', default='wlan0', dest="interface", metavar='interface',\
help="Select which interface to use. Defaults to wlan0.", action='store')
PARSER.add_argument('-f', metavar='filepath', dest="capfile", action='store',\
help='Read from a pcap file instead of live capture.')
PARSER.add_argument('-d', dest="delay_packets", action='store_true',\
help="Use the original delay between packets when reading from a file.")
PARSER.add_argument('-h', default='localhost', dest="server_host", metavar='host',\
help="Set host address for the webserver. Defaults to localhost.", action='store')
PARSER.add_argument('-p', default=8080, type=int, dest="server_port", metavar='port',\
help="Set port number for the webserver. Defaults to 8080.", action='store')
PARSER.add_argument('-v', dest="verbose", action='count',\
help="Verbose; can be used up to 3 times to set the verbose level.")
PARSER.add_argument('-s', dest="server", action='store_true',\
help='''Run in server mode; packets will also be handled and analyzed when
there are no clients connected to the webinterface. Usefull for testing.''')
PARSER.add_argument('-m', dest="allow_multiple", action='store_true',\
help="Allow multiple clients to be connected to the webinterface at the same time.")
PARSER.add_argument('-w', metavar='filepath', dest="output_file", action="store",\
help="Write all found URLs to a file.")
PARSER.add_argument('-sd', dest="server_debug", action="store_true",\
help="Run the Flask webserver in debug mode.")
PARSER.add_argument("--help", dest="help", action="store_true",\
help="Show this help message and exit.")
PARSER.add_argument('--version', action='version', version='%(prog)s version 0.2',\
help="Show program's version number and exit")
ARGS = PARSER.parse_args()

# --help argument shows help and exits
if ARGS.help:
    PARSER.print_help()
    sys.exit(0)


SEEN_SSID_REQUESTS = []
SEEN_HOSTNAMES = []
IP_TO_HOSTNAME = {}

STATISTICS = []

CONNECTIONS = {} # Stores open connections to clients

PACKETS_IN = 0
PACKETS_OUT = 0

APP = Flask(__name__) # The server object
if ARGS.server_debug: APP.debug = True

class FlaskServer(threading.Thread):
    """ Class that handles the Flask server,
    used to show the webinterface """
    def __init__(self, server_host, server_port):
        threading.Thread.__init__(self)
        self.event = threading.Event()
        self.server_host = server_host
        self.server_port = server_port
        self.daemon = True

    @APP.route('/socket.io/<path:remaining>')
    def snuffel_socket(remaining):
        socketio_manage(request.environ, {'/snuffel':Communication}, request)
        return 'done'

    @APP.route('/')
    def main_page():
        """ Show the main page in the webinterface """
        return render_template('index.html') if len(CONNECTIONS) == 0 or ARGS.allow_multiple else render_template('in_use.html')

    def run(self):
        """ Start the Flask server """
        try:
            if ARGS.verbose >= 1: print "Starting socket server on %s:%s" % (self.server_host, self.server_port)
            while not self.event.is_set():
                SocketIOServer((self.server_host, self.server_port), APP, resource="socket.io").serve_forever()
        except Exception as e:
            print "Can't start the server: ", e.strerror
            self.stop()

    def stop(self):
        """ Stop the Flask server """
        if ARGS.verbose >= 1: print "Stopping Flask server thread"
        self.event.set()

#======================================================
# Socket communication namespace
#======================================================
class Communication(BaseNamespace, BroadcastMixin):
    """ Class that handles communication with the
    webinterface through the Flask server's socket connection """

    def recv_connect(self):
        """ Triggered wehen a client connects to the webinterface """
        global CONNECTIONS
        CONNECTIONS[id(self)] = self
        self.broadcast_event('open_connections', {'value':len(CONNECTIONS)})

    #======================================================
    # Client disconnects
    def recv_disconnect(self):
        """ Triggered when a client disconnects """
        try:
            del CONNECTIONS[id(self)]
            self.broadcast_event('open_connections', {'value':len(CONNECTIONS)})
        except:
            pass

    def on_restart(self):
        """ Triggered when webinterface requests Snuffel to restart the device """
        if ARGS.verbose >= 1: print "Restart Snuffel device"
        #os.system('sudo reboot')

    def on_shutdown(self):
        """ Triggered when webinterface requests Snuffel to shut down the device """
        if ARGS.verbose >= 1: print "Shutdown Snuffel device"
        #os.system('sudo shutdown -h now')

    def on_toggle_sniffing(self, data):
        """ Triggered when webinterface requests Snuffel to start / stop sniffing """
        if ARGS.verbose >= 1: print "Start sniffing" if data else "Stop sniffing"

    def on_get_statistics(self):
        """ Triggered when webinterface requests statistics about the sniffing"""
        if ARGS.verbose >= 1: print "get_statistics"
        global STATISTICS
        STATISTICS = [[u'Packets sent', PACKETS_OUT], [u'Packets received', PACKETS_IN]]
        self.broadcast_event('get_statistics', json.dumps(STATISTICS))

    def on_reset_statistics(self):
        """ Triggered when webinterface requests to reset and clear the statistics """
        if ARGS.verbose >= 1: print "reset_statistics"
        global PACKETS_IN, PACKETS_OUT
        PACKETS_IN = 0
        PACKETS_OUT = 0


    def on_get_available_networks(self):
        """ Triggered when webinterface requests a list of available wifi networks """
        if ARGS.verbose >= 1: print 'Requesting network list'
        response = get_available_networks()
        self.broadcast_event('get_available_networks', response)

    def on_connect_to_network(self, data):
        """ Triggered when webinterface requests Snuffel to connect to a specified wifi network """
        connect_to_network(data['ssid'], data['passkey'])

#======================================================
# The packet retrieval and analyzer thread
#======================================================
class PacketAnalyzer(threading.Thread):
    """ Class to analyze the wifi traffic, looking for URLs, images, etc. """

    def __init__(self):
        threading.Thread.__init__(self)
        self.event = threading.Event()
        self.daemon = True
        self.seen_url_buffer = [] # Keeps track of the last 25 urls seen, to prevent doubles
        self.own_ip = socket.gethostbyname(socket.gethostname())
        self.image_extentions = ['.jpg', '.jpeg', '.gif', '.png', '.bmp', '.svg', '.ico']
        self.url_ignore_endings = ['.js', '.css', '.woff']
        self.ignore_keywords = ['min.js', 'min.css']

        # Determine packetSource - live capture or pcap file
        self.packetsource = None
        if ARGS.capfile != None:
            try:
                with open(ARGS.capfile):
                    if ARGS.verbose >= 1: print "Using file: %s" % ARGS.capfile
                    self.packetsource = pyshark.FileCapture(ARGS.capfile, lazy=True)
            except IOError:
                print "Couldn't find or open the pcap file '%s'" % ARGS.capfile
                exit()
        else:
            if ARGS.verbose >= 1: print "Starting capture on interface '%s'" % ARGS.interface
            self.capture = pyshark.LiveCapture(interface=ARGS.interface)
            self.packetsource = self.capture.sniff_continuously()

    def run(self):
        global PACKETS_IN, PACKETS_OUT
        packet = None

        while not self.event.is_set():
            if not ARGS.capfile: # live capture
                packet = self.packetsource.next()
            else: # read from a pcap / pcapng file
                next_packet = self.packetsource.next()
                # wait original delay between packets if the -d flag
                # has been set
                if ARGS.delay_packets and packet is not None: 
                    try: # skip delay if no sniff_time
                        time_delta = next_packet.sniff_time - packet.sniff_time
                        if ARGS.verbose >= 2: print "Sleeping %f seconds until next packet." % time_delta.total_seconds()
                        time.sleep(time_delta.total_seconds())
                    except Exception as e: print "Delay error: ", e
                packet = next_packet

            # Only actually analyze packet when a client is connected
            # or when in server mode. Otherwise, packet will be discarted
            # without being analyzed, to prevent build up of old packets
            if len(CONNECTIONS) > 0 or ARGS.server:
                # Determine if a package was going in or out,
                # and keep track of the amount of packages
                try:
                    if packet.ip.src == self.own_ip:
                        PACKETS_IN = PACKETS_IN + 1
                except: pass
                try:
                    if packet.ip.dst == self.own_ip:
                        PACKETS_OUT = PACKETS_OUT   + 1
                except: pass

                # Some of the layer types seen but not used in the below if/elif structure
                # DATA, BJNP, SSL, IMAGE-GIF, DATA-TEXT-LINES, PNG, IMAGE-JFIF, ARP, NBNS, MEDIA

                # Skip malformed packages, as their contents
                # might break stuff
                if packet.highest_layer.upper() == 'MALFORMED':
                    continue

                # Search for probe requests in the WLAN_MGT layer
                elif packet.highest_layer.upper() == "WLAN_MGT":
                    try:
                        ssid = self.get_ssid_from_wlan_mgt(packet.wlan_mgt)
                        if ssid != None:
                            self.send_new_item('probe_request', ssid)
                    except: pass

                # This layer is unique for the Dropbox client
                elif packet.highest_layer == 'DB-LSP-DISC':
                    if ARGS.verbose >= 2: print "Service: Dropbox"
                    self.send_new_item('service', 'dropbox')

                # Search for and handle URLS in the HTTP layer
                elif packet.highest_layer == 'HTTP':
                    url = ''
                    try:
                        url = packet.http.location
                    except:
                        try:
                            url = packet.http.request_full_uri
                        except: pass

                    # Check if the found url is not empty, doesn't contain keywords
                    # from ignore_keywords, and does not end in anything from url_ignore_endings
                    if url != '' and all(x not in url.lower() for x in self.ignore_keywords)\
                        and not any(url.endswith(x) for x in self.url_ignore_endings):

                        # Ignore if url was included in the last 25 urls seen,
                        # to prevent too many doubles
                        if not url in self.seen_url_buffer:
                            self.seen_url_buffer.append(url)
                            if len(self.seen_url_buffer) > 25: self.seen_url_buffer.pop(0)

                            # Check if the URL is an image, or webpage / file
                            try:
                                if 'image' in packet.http.accept or any(url.endswith(x) for x in self.image_extentions):
                                    if ARGS.verbose >= 2: print "Image: %s" % url
                                    self.send_new_item('img', url)
                                else:
                                    if ARGS.verbose >= 2: print "Website: %s" % url
                                    self.send_new_item('url', url)
                            except: pass
                    else:
                        if ARGS.verbose >= 3 and url != '': print "Ignore: %s" % url

                # Try to get a hostname
                elif packet.highest_layer == 'BOOTP':
                    hostname = self.get_hostname_from_bootp(packet.bootp, packet.ip.src)
                    if hostname != None:
                        self.send_new_item('hostname', hostname)

                # Get imap info, not analyzed yet
                elif packet.highest_layer == 'IMAP':
                    self.send_new_item('email', 'IMAP something')

    def stop(self):
        """ Stop the packet analyzer """
        self.event.set()

    # Kind of a hack, but I didn't find another way to access this data
    def get_ssid_from_wlan_mgt(self, obj):
        """ Search for an SSID in the wlan_mgt layer
        of a probe request """
        for child in obj.xml_obj.getchildren():
            for grandchild in child.iterchildren():
                for greatgrandchild in grandchild.iterchildren():
                    if "SSID: " in greatgrandchild.attrib['showname']:
                        ssid = greatgrandchild.attrib['showname'][6:]
                        if ssid not in SEEN_SSID_REQUESTS and len(ssid) > 0 and "[truncated]" not in ssid:
                            SEEN_SSID_REQUESTS.append(ssid)
                            return ssid
                        else: return None # Return None to end these for loops

    # almost the same as the get_ssid_from_wlan_mgt function,
    # but one level less deep
    def get_hostname_from_bootp(self, obj, packet_ip):
        """ Search for a hostname in the BOOTP layer
        and match it to an IP if possible """        
        for child in obj.xml_obj.getchildren():
            for grandchild in child.iterchildren():
                if "Host Name: " in grandchild.attrib['showname']:
                    hostname = grandchild.attrib['show']
                    if hostname not in SEEN_HOSTNAMES and len(hostname) > 0 and "[truncated]" not in hostname:
                        SEEN_HOSTNAMES.append(hostname)
                        if packet_ip != "0.0.0.0": # If we know where it came from, store the hostname / ip relation
                            if ARGS.verbose >= 3: print "Matched hostname %s with ip %s" % (hostname, packet_ip)
                            global IP_TO_HOSTNAME                            
                            IP_TO_HOSTNAME[packet_ip] = hostname
                        return hostname
                    else: return None # Return None to end these for loops

    def send_new_item(self, item_type, item_value):
        """ Send a message to the webinterface """
        # This Try:Except is for debugging and should be removed in the end,
        # as messages shouldn't be able to brake anything
        try:
            item_time = time.strftime("%H:%M:%S")
            if ARGS.verbose >= 3: print "Sending item: %s, %s" % (item_type, item_value)
            if ARGS.output_file: os.system('echo "%s,%s,%s" >> %s' % (item_time, item_type, item_value, ARGS.output_file))
            if len(CONNECTIONS) > 0:
                CONNECTIONS.values()[0].broadcast_event('new_item', {'itemType':item_type, 'itemValue':item_value, 'itemTime':item_time})
        except Exception as e: print e


#======================================================
# Functions dealing with the wifi network
#======================================================
def get_available_networks():
    """ Returns a list of available wifi networks """
    try:
        ssids = [[cell.ssid, cell.encrypted] for cell in Cell.all('wlan1')]
    except:
        print "Error getting available; is iwlist available on your machine?"
        sys.exit(0)
    json_output = json.dumps(ssids)
    return json_output

def connect_to_network(ssid, passkey=""):
    """ Try to connect to the given wifi network """
    if ARGS.verbose >= 1: print "Connect to %s with passKey '%s'" % (ssid, passkey)
    #fake a network list, as OSX doesn't have iwlist
    # I should be able to create this list in one line, right?
    try:
        cells = Cell.all('wlan1')
    except:
        print "Error connecting to wifi; is iwlist available on your machine?"
        sys.exit(0)

    for cell in cells:
        print "CHECK %s with %s" % (cell.ssid, ssid)
        if cell.ssid == ssid:
            if passkey != "":
                scheme = Scheme.for_cell('wlan1', ssid, cell, passkey)
            else:
                scheme = Scheme.for_cell('wlan1', ssid, cell)
            scheme.save()
            scheme.activate()

#======================================================
# Start the program
#======================================================
def main():
    """ Main function that starts the Flask server and
    the packet analyzer """
    try:
        flask_server = FlaskServer(ARGS.server_host, ARGS.server_port)
        flask_server.start()

        packet_analyzer = PacketAnalyzer()
        packet_analyzer.start()

        while not flask_server.event.isSet() and not packet_analyzer.event.isSet():
            # Loop while the threads are running
            time.sleep(100)

    except (KeyboardInterrupt, SystemExit):
        flask_server.stop()
        sys.exit("Received keyboard interrupt, Snuffel will now quit.")

if __name__ == "__main__":
    main()
