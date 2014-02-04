var running = false;
var isConnected = false;

var wifiNetworks = [];
var waitingForWifiList = false;

var socket = io.connect(location.hostname);

//==========================================================
// Send a command / value pair to the server
//==========================================================
function cmdToServer(cmdName, cmdValue){
	socket.emit('cmdToServer', {
		'name': cmdName,
		'value': cmdValue
	});
}

//==========================================================
// Show a simple dialog with a message and optional progressbar
//==========================================================
function setGenericDialog(title, message, showProgressbar){
	$('.genericDialog').dialog('option', 'title', title);
	$('.genericDialogMessage').html(message);
	showProgressbar ? $('.genericDialogProgressbar').show() : $('.genericDialogProgressbar').hide();
	$('.genericDialog').dialog('open');
}

$(document).ready(function() {

	//==========================================================
	// On connect / disconnect toggle notification color
	//==========================================================
	socket.on('connect',function() {
		isConnected = true;
		$('.connectedIndicator').css('background', '#006006');
	});
	socket.on('disconnect', function(){
		isConnected = false;
		$('.connectedIndicator').css('background-color', '#660000');
	});

	//==========================================================
	// Receive list of wifi networks
	// data = {{wifiNetworks}}
	//==========================================================
	socket.on('wifiNetworks', function ( data ){
		var s = $('<select />', {'class': 'wifiNetworkList'});
		for(var val in data) {
			wifiNetworks.push(data[val]);
			$('<option />', {value: val, text: data[val]}).appendTo(s);
		}
		$('.wifiNetworkListHolder').html(s);
		if(!waitingForWifiList) return;
		if($('.genericDialog').dialog('isOpen')) $('.genericDialog').dialog('close');
		$('.wifiSelectionDialog').dialog('open');
	});

	//==========================================================
	// Receive list of wifi networks
	// data = {{wifiNetworks}}
	//==========================================================
	socket.on('statistics', function ( data ){
		$('.infoDialogMessage').html(data.statistics);
		$( ".infoDialog" ).dialog( "open" );

	});

	//==========================================================
	// Receive a new message
	// data = {time, type, contents}
	//==========================================================
	socket.on('newMessage', function ( data ) {
		var obj = '<div class="message">';
		obj += '<div class="titleBar floatFix">';
		if(data.msgType === 'url'){
			obj +='<div class="title">URL found</div><div class="time">'+data.timestamp+'</div></div>';
			obj +='<div class="contents">'+data.msg+'</div>';
		}else if(data.msgType === 'txt'){
			obj +='<div class="title">Plain text found</div><div class="time">'+data.timestamp+'</div></div>';
			obj +='<div class="contents">'+data.msg+'</div>';
		}else if(data.msgType === 'img'){
			obj +='<div class="title">Image found</div><div class="time">'+data.timestamp+'</div></div>';
			obj +='<div class="contents"><img src="'+data.msg+'" /></div>';
		}
		obj +='</div>';
		$( ".messagesHolder" ).prepend(obj);
		$('.messages').html('timestamp: '+data.timestamp+'<br />'+'msgType: '+data.msgType+'<br />'+'message: '+data.msg+'<br />');
	});

	//==========================================================
	// Receive a reload command from server
	// data = {}
	//==========================================================
	socket.on('reload', function ( data ) {
		window.location.reload( true );
	});

	//==========================================================
	// Start / Stop and settings buttons at bottom of page
	//==========================================================
	$( ".startStopBtn" ).click(function( event ) {
		event.preventDefault();
		running = !running;
		running ? $(this).button( "option", "label", "stop" ) : $(this).button( "option", "label", "start" );
		socket.emit('status', {'status': running});
	});

	$( ".infoBtn" ).click(function( event ) {
		event.preventDefault();
		socket.emit('askForStatistics');
	});

	$( ".settingsBtn" ).click(function( event ) {
		event.preventDefault();
		$( ".settingsMenuDialog" ).dialog( "open" );
	});

	//==========================================================
	// Set defaults for all dialogs
	//==========================================================
	$('.dialog').dialog({
			dialogClass: "no-close",
		resizable: false,
			show: 500,
			hide: 500,
			draggable: false,
		position: {
			my: "top",
			at: "top+5%",
			of: "body"
		},
		modal: true,
		autoOpen: false,
		width: '90%'
	});

	//==========================================================
	// infoDialog for showing some stats
	//==========================================================
	$( ".connectedIndicatorDialog" ).dialog({
		title: 'Connection status',
		buttons: [
			{
				text: "Close",
				click: function() {
					$(this).dialog('close');
				}
			}
		]
	});
	$('.connectedIndicator').click(function(){
		if(isConnected){
			$('.connectedIndicatorDialog').html('The app is connected to the server.');
		}else{
			$('.connectedIndicatorDialog').html('The app is not connected to the server.');
		}
		$('.connectedIndicatorDialog').dialog('open');
	});

	//==========================================================
	// infoDialog for showing some stats
	//==========================================================
	$( ".infoDialog" ).dialog({
		title: 'Statistics',
		buttons: [
			{
				text: 'Export',
				click: function() {
					$(this).dialog('close');
					setGenericDialog('Exporting', 'Exporting your statistics...<br />(Not doing anything yet)', true);
				}
			},
			{
				text: 'Clear',
				click: function() {
					$(this).dialog('close');
					$('.infoClearConfirmDialog').dialog('open');
				}
			},
			{
				text: "Close",
				click: function() {
					$(this).dialog('close');
				}
			}
		]
	});

	//==========================================================
	// infoClearConfirmDialog to check if you really want 
	// to clear the stats
	//==========================================================
		$( ".infoClearConfirmDialog" ).dialog({
			title: 'Clear statistics',
		buttons: {
			"Clear": function() {
				socket.emit('clearStatistics');
				$( this ).dialog( "close" );
			},
			Cancel: function() {
				$( this ).dialog( "close" );
				$('.infoDialog').dialog('open');
			}
		}
	});

	//==========================================================
	// genericDialog for showing different messages
	//==========================================================
	$( ".genericDialog" ).dialog({
		buttons: [
			{
				text: "Cancel",
				click: function() {
					waitingForWifiList = false;
					$(this).dialog('close');
				}
			}
		]
	});

	//==========================================================
	// wifiSelectionDialog showing list of available networks
	//==========================================================
	$( ".wifiSelectionDialog" ).dialog({
		title: 'Connect to wifi network',
		buttons: [
			{
				text: "Connect",
				click: function() {
					var index = $('.wifiNetworkList').val();
					$(this).dialog('close');
					setGenericDialog('Connecting', 'Connecting to <b>'+wifiNetworks[index]+'</b>...', true);
					socket.emit('connectToWifi', {
						'networkIndex': index,
						'networkName': wifiNetworks[index],
						'networkPassword': $('.wifiNetworkPassword').val()
					});
				}
			},
			{
				text: "Rescan",
				click: function() {
					$(this).dialog('close');
					setGenericDialog('Scanning', 'Scanning for wifi networks... (at the moment just a 4 second time-out)', true);
					waitingForWifiList = true;
					socket.emit('askForWifiNetworks');
				}
			},
			{
				text: "Cancel",
				click: function() {
					$( this ).dialog( "close" );
				}
			}
		]
	});


	$( ".wifiConnectingDialog" ).dialog({
		title: 'Connecting...',
		buttons: [
			{
				text: "Cancel",
				click: function() {
					$(this).dialog('close');
				}
			}
		]
	});

	$( ".setupWifiBtn" ).click(function( event ) {
		if($('.settingsMenuDialog').dialog('isOpen')) $('.settingsMenuDialog').dialog('close');
		setGenericDialog('Scanning', 'Scanning for wifi networks... (at the moment just a 4 second time-out)', true);
		$('.wifiNetworkListHolder').html('');
		waitingForWifiList = true;
		socket.emit('askForWifiNetworks');
		event.preventDefault();
	});

	//==========================================================
	// Enable buttons and progress bar
	//==========================================================
	$('button').button();
	$( ".genericDialogProgressbar" ).progressbar({
		value: false
	}).find( ".ui-progressbar-value").css('background', '#aaaaaa');

	//==========================================================
	// settingsMenuDialog showing the list of settings
	//==========================================================
	$( ".settingsMenuDialog" ).dialog({
		title: 'Settings',
		buttons: [
			{
				text: "Close",
				click: function() {
					$( this ).dialog( "close" );
				}
			}
		]
	});
});
