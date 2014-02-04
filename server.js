/***********************************************************
/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\
.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'
     
       mmmm                  m""    m""         ""#   
      #"   " m mm   m   m  mm#mm  mm#mm   mmm     #   
      "#mmm  #"  #  #   #    #      #    #"  #    #   
          "# #   #  #   #    #      #    #""""    #   
      "mmm#" #   #  "mm"#    #      #    "#mm"    "mm

.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'.'
/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\
***********************************************************/

//==========================================================
// Set initial variables
//==========================================================
var debug = false;
var HTTPPORT = 80;

//==========================================================
// Process command line arguments:
//  Check for argument -d for debug
//  Check for argument -p <PORT> for HTTPPORT
//==========================================================
process.argv.forEach(function (val, index, array) {
	if(val == "-d") debug = true;
    if(val == "-p") {
       if(! isNaN(parseInt(array[index+1]))) {
           HTTPPORT = parseInt(array[index+1]);
       } else {
           if(debug) console.log('Command line argument -p requires a port number');
           process.exit(1);
       }
    }
});


//==========================================================
// Find the ip for this computers network interface
// (grabs first one found, wlan0 in OSX)
//==========================================================
var os=require('os');
var ifaces=os.networkInterfaces();
var IP = '';
for (var dev in ifaces) {
	var alias=0;
	ifaces[dev].forEach(function(details){
		if (details.family==='IPv4') {
			if(details.address != '127.0.0.1' && IP === '') {
				IP = details.address;
			}
			++alias;
		}
	});
}
if(debug) console.log('Starting node.js server on address '+IP+':'+HTTPPORT);

//==========================================================
// Import required modules and set up express
//==========================================================
var express = require("express"),
	socket = require('socket.io'),
	app = express();

app.configure(function(){
	app.use(express.static(__dirname + '/'));
});

var server = app.listen(HTTPPORT);
var io = socket.listen(server, {'log level':1, log: debug});

//==========================================================
// Setup socket behaviours on connect
//==========================================================
var isConnected = false;
var connections = 0;

var startTime = 0;
var totalSecondsRunning = 0;

//var connectedSocket = '';

io.sockets.on('connection', function (socket) {
	//connectedSocket = socket;
	connections++;
	isConnected = true;

	if(debug) console.log('A device connected.');

	//==========================================================
	// Function to start and stop
	// data = {running}
	//==========================================================
	socket.on('status', function ( data ){
		if(data.status){
			if (debug) console.log('start running');
			startTime = now();
		}else{
			if (debug) console.log('stop running');
			var addSeconds = now()-startTime;
			totalSecondsRunning += addSeconds;
			startTime = 0;
		}
	});

	//==========================================================
	// Receive new message from python to display on webpage
	// data = {type, time, title, contents}
	//==========================================================
	socket.on('newMsg', function (data) {
		if(debug){
			console.log("Socket incoming msg from python");
			console.log("timestamp: "+data.timestamp);
			console.log("msgType: "+data.msgType);
			console.log("msg: "+data.msg);
		}
		//socket.emit('newMessage', { 'timestamp': data.timestamp, 'msgType': data.msgType, 'msg': data.msg });
		socket.broadcast.emit('newMessage', data);
	});

	//==========================================================
	// Send command from webpage to Python
	// data = {command}
	//==========================================================
	socket.on('cmdToServer', function (data) {
		if(debug){
			console.log('cmdName: '+data.name);
			console.log('cmdValue: '+data.value);
		}
		//socketio.sockets.emit('inputCmd', data);
		socket.emit('inputCmd', data);
	});

	//==========================================================
	// Send list of statistics
	// data = {0, 1, 2, 3, etc.}
	//==========================================================
	socket.on('askForStatistics', function (data){
		var tempTime = totalSecondsRunning;
		if (startTime !== 0) tempTime += now()-startTime;
		console.log('tempTime: '+toHHMMSS(tempTime));

		/*jshint multistr: true */
		var statistics = 'Total time: '+ toHHMMSS(tempTime)+'<br />\
		Some other stats here: ...<br />\
		End some more: ...';
		socket.emit('statistics', { 'statistics': statistics});
	});

	//==========================================================
	// Clear the statistics
	// data = {}
	//==========================================================
	socket.on('clearStatistics', function (data){
		if(debug) console.log('Clearing statistics');
		console.log("running before: "+totalSecondsRunning);
		totalSecondsRunning = 0;
		console.log("running after: "+totalSecondsRunning);
	});

	//==========================================================
	// Send list of availble wifi networks to GUI
	// data = {networks}
	//==========================================================
	socket.on('askForWifiNetworks', function (data){
		//socket.emit('wifiNetworks', {'network one', 'network two', 'network three'});
		//socket.emit('wifiNetworks', { 0: 'network 1', 1:'network 2', 2:'network 3'});		

		setTimeout( function(i){
            socket.emit('wifiNetworks', { 0: 'network 1', 1:'network 2', 2:'network 3'});
        }, 4000);
	});

	socket.on('connectToWifi', function (data){
		console.log("Connect to wifi with index: "+data.networkIndex);
		console.log("Wifi name: "+data.networkName);
		console.log("Wifi password: "+data.networkPassword);
	});

	//==========================================================
	// Function to refresh all the pages
	// data = {}
	//==========================================================
	socket.on('reload', function ( ){
		socket.broadcast.emit('reload');
	});

	//==========================================================
	// Device disconnected
	//==========================================================
	socket.on('disconnect', function () {
		connections--;
		console.log('Disconnecting');
		console.log('Connections left: '+connections);
		if(connections <= 0){
			console.log('All clients disconnected');
			isConnected = false;
		}
	});
});

//==========================================================
// Handle how Node exits 
//==========================================================
//process.on('exit', function(){
//  if(debug) console.log("Exit handler");
//});
process.on('SIGINT', function () {
	if(debug) console.log("SIGINT, exiting");
	process.exit();
});

function now(){
	return Math.round((new Date()).getTime()/1000);
}
function toHHMMSS(value){
    var sec_num = parseInt(value, 10); // don't forget the second param
    var hours   = Math.floor(sec_num / 3600);
    var minutes = Math.floor((sec_num - (hours * 3600)) / 60);
    var seconds = sec_num - (hours * 3600) - (minutes * 60);
    console.log('sec_num: '+sec_num);
    if (hours   < 10) {hours   = "0"+hours;}
    if (minutes < 10) {minutes = "0"+minutes;}
    if (seconds < 10) {seconds = "0"+seconds;}
    var time    = hours+':'+minutes+':'+seconds;
    return time;
}
