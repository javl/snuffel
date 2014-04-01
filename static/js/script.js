
var isSniffing = false;
var isConnected = false;
var openConnections = 0;

var wifiNetworks = [];
var waitingForWifiList = false;

// var socket = io.connect(location.hostname);
var socket = io.connect('/snuffel');

//==========================================================
// Show a simple dialog with a message and optional progressbar
//==========================================================
function set_generic_dialog(title, message, showProgressbar, buttonText){
	$('.genericDialog').dialog('option', 'title', title);
	$('.genericDialog').dialog('option', 'message', "FOOBAR");
	$('.genericDialog').parent().find('.ui-button-text').text(buttonText);
	$('.genericDialogMessage').html(message);
	showProgressbar ? $('.genericDialogProgressbar').show() : $('.genericDialogProgressbar').hide();
	$('.genericDialog').dialog('open');
}

//==========================================================
// Start code when page is fully loaded
//==========================================================
$(document).ready(function() {

	//==========================================================
	// On connect / disconnect toggle notification color
	//==========================================================
	socket.on('connect',function() {
		isConnected = true;
		$('.connectedIndicator').css('background', '#00ff00');
		
	});

	socket.on('disconnect', function(){
		isConnected = false;
		$('.connectedIndicator').css('background', '#ff0000');
	});

	//==========================================================
	// Receive and display the amount of logged in devices
	//==========================================================
	socket.on('open_connections', function(data){
		openConnections = data.value;
		//$('.connectedIndicator').html(openConnections);
		$('.connectedIndicator').button('option', 'label', openConnections);
	});

	//==========================================================
	// Receive list of wifi networks
	// data = {{wifiNetworks}}
	//==========================================================
	socket.on('get_available_networks', function ( data ){
        $('.wifiNetworkList').html('').append("<option selected='true' disabled='disabled'>Select a wifi-network</option>");
        $.parseJSON(data).forEach(function(item) { // build list of network names
        	item[1] ? isProtected = true : isProtected = false;
            $('.wifiNetworkList').append("<option data-protected='"+isProtected+"' value='"+item[0]+"'>"+item[0]+"</option>");
        });
		if(!waitingForWifiList) return;
		if($('.genericDialog').dialog('isOpen')) $('.genericDialog').dialog('close');
		$('.wifiSelectionDialog').dialog('open');
	});

	//==========================================================
	// Receive statistics (json)
	// data = '[["stat 1", "ONE"], ["stat 2", "TWO"], etc]'
	//==========================================================
	socket.on('get_statistics', function ( data ){
		$('.statisticsDialogList').html('');
        $.parseJSON(data).forEach(function(item) {
            $('.statisticsDialogList').append("<li><b>"+item[0]+"</b>: "+item[1]+"</li>");
        })
		//$('.statisticsDialogList').append('</ul>');
		$( ".statisticsDialog" ).dialog( "open" );
	});

	//==========================================================
	// Receive a new message
	// data = {item_type, item_value, item_time}
	//==========================================================
	socket.on('new_item', function ( data ) {
		var obj = '<div class="message">';
		console.log(data);
		if (data.device_id != ''){
			data.device_id = data.device_id+' - ';
		}
		obj += '<div class="titleBar floatFix">';
		if(data.item_type === 'url'){
			obj += '<div class="title">URL found</div><div class="time">'+data.device_id+data.item_time+'</div></div>';
			obj += '<div class="contents">'+data.item_value+'</div>';
		}else if(data.item_type === 'img'){
			obj +='<div class="title">Image found</div><div class="time">'+data.device_id+data.item_time+'</div></div>';
			obj +='<div class="contents"><img src="'+data.item_value+'" /></div>';
		}else if(data.item_type === 'service'){
			obj +='<div class="title">Service found</div><div class="time">'+data.device_id+data.item_time+'</div></div>';
			obj +='<div class="contents">'+data.item_value+'</div>';
		}else if(data.item_type === 'tracker'){
			obj +='<div class="title">Tracker found</div><div class="time">'+data.device_id+data.item_time+'</div></div>';
			obj +='<div class="contents">'+data.item_value+'</div>';
		}else if(data.item_type === 'probe_request'){
			obj +='<div class="title">Probe request found</div><div class="time">'+data.device_id+data.item_time+'</div></div>';
			obj +='<div class="contents">'+data.item_value+'</div>';
		}else if(data.item_type === 'hostname'){
			obj +='<div class="title">Hostname found</div><div class="time">'+data.device_id+data.item_time+'</div></div>';
			obj +='<div class="contents">'+data.item_value+'</div>';
		}
		obj +='</div>';
		//$( ".messagesHolder" ).prepend(obj);
		$( ".messagesHolder" ).prepend(obj);
		$('.messages').html('timestamp: '+data.item_time+'<br />'+'msgType: '+data.item_type+'<br />'+'message: '+data.item_value+'<br />');
	});

	//==========================================================
	// Receive a reload command from server
	// data = {}
	//==========================================================
	socket.on('reload', function ( data ) {
		window.location.reload( true );
	});

	//==========================================================
	// Set defaults for all dialogs
	//==========================================================
	$('.dialog').dialog({
		dialogClass: "no-close",
		resizable: false,
		show: false,
		hide: false,
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
	// Prepare the connection indicator dialog (bottom right button)
	//==========================================================
	$( ".connectedIndicatorDialog" ).dialog({
		title: 'Connection status',
		buttons: [
			{
				text: "Close", click: function() {
					$(this).dialog('close');
				}
			}
		]
	});

	//==========================================================
	// statisticsDialog for showing some stats
	//==========================================================
	$( ".statisticsDialog" ).dialog({
		title: 'Statistics',
		buttons: [
			{
				text: 'Refresh', click: function() {
					socket.emit('get_statistics');					
				}
			},
			{
				text: 'Export', click: function() {
					$(this).dialog('close');
					set_generic_dialog('Exporting', 'Exporting statistics isn\'t implemented yet.', true, 'Cancel');
				}
			},
			{
				text: 'Reset', click: function() {
					$(this).dialog('close');
	            	confirm_dialog('Are you sure you want to reset the statistics? This can\'t be undone.', 
            			function(){ socket.emit('reset_statistics'); });	            	
				}
			},
			{
				text: "Close", click: function() {
					$(this).dialog('close');
				}
			}
		]
	});

	//==========================================================
	// genericDialog for showing different messages
	//==========================================================
	$( ".genericDialog" ).dialog({
		buttons: [
			{
				text: "Cancel", click: function() {
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
				text: "Connect", click: function() {
					//$(this).dialog('close');
					var selected_network = $('.wifiNetworkList').val();
					if(selected_network == 'Select a wifi-network'){
						set_generic_dialog('Error', 'Please select a network from the list.', false, 'OK');
					}else{
						set_generic_dialog('Connecting', 'Connecting to <b>'+selected_network+'</b>...', true, 'Cancel');
						socket.emit('connect_to_network', {
							//'networkIndex': index,
							'ssid': selected_network,
							'passkey': $('.wifiNetworkPassword').val()
						});
					}
				}
			},
			{
				text: "Rescan", click: function() {
					$(this).dialog('close');
					set_generic_dialog('Scanning', 'Scanning for wifi networks...', true, 'Cancel');
					waitingForWifiList = true;
		            socket.emit('get_available_networks')
				}
			},
			{
				text: "Cancel", click: function() {
					$( this ).dialog( "close" );
				}
			}
		]
	});

	//==========================================================
	// Dialog to confirm / cancel certain actions
	// Will run the proviced callback function on Yes
	//==========================================================
	function confirm_dialog(msg, callback){
		$(".confirmationDialog").html(msg).dialog('option', 'title', 'Confirm');
        $(".confirmationDialog").dialog('option', 'buttons', { 
            "Yes": function() { 
                $( this ).dialog( "close" );
                callback();
            }, 
            'Cancel': function(){
                $( this ).dialog( "close" );
            }  
        });
        $(".confirmationDialog").dialog("open");
    }

	//==========================================================
	// Actions for all the different buttons
	//==========================================================	
	$( '.actionBtn').click(function(event){
		event.preventDefault();
		switch ($(this).data('action')){
			case 'setup_wifi':
				if($('.mainMenuDialog').dialog('isOpen')) $('.mainMenuDialog').dialog('close');
				set_generic_dialog('Scanning', 'Scanning for wifi networks...', true, 'Cancel');
				waitingForWifiList = true;
        		socket.emit('get_available_networks')
				break;
			case 'select_language':
				alert('This function doesn\'t work yet');
				break;
			case 'restart_pi':
            	confirm_dialog('Are you sure you want to restart the Snuffel device?', 
            		function(){ $('body').fadeOut(); socket.emit('restart'); });
				break;
			case 'shutdown_pi':
            	confirm_dialog('Are you sure you want to shutdown the Snuffel device?', 
            		function(){ $('body').fadeOut(); socket.emit('shutdown'); });				
				break;
			case 'toggle_sniffing':
				isSniffing = !isSniffing;
				isSniffing ? $(this).button( "option", "label", "stop" ) : $(this).button( "option", "label", "start" );
				socket.emit('toggle_sniffing', isSniffing);
				break;
			case 'get_statistics':
				socket.emit('get_statistics');
				break;
			case 'open_menu':
				$( ".mainMenuDialog" ).dialog( "open" );
				break;
			case 'show_connection_status':
				var msg = 'Not connected to the server.';
				if(isConnected){
					openConnections === 1 ? msg = 'Connected to the server, with no other devices.' : msg = 'Connected to the server, with '+(openConnections-1)+' other device(s).';
				}
				$('.connectedIndicatorDialog').html(msg).dialog('open');
				break;
		}
	})

	//==========================================================
	// Actions when selecting a wifi network from the list:
	// Show / hide the password field, depending on the selected network
	//==========================================================
	$(".wifiNetworkList").change(function( event ){
		if ($(this).children(":selected").data('protected')){
			$('.wifiNetworkPassword').val('');
			$('.wifiNetworkPasswordBlock').show();
		}else{
			$('.wifiNetworkPasswordBlock').hide();
			$('.wifiNetworkPassword').val('');
		}
	});

	//==========================================================
	// Enable buttons and progress bar
	//==========================================================
	$('button').button();
	$( ".genericDialogProgressbar" ).progressbar({
		value: false
	}).find( ".ui-progressbar-value").css('background', '#aaaaaa');

	//==========================================================
	// Prepare mainMenuDialog showing the list of settings
	//==========================================================
	$( ".mainMenuDialog" ).dialog({
		title: 'Settings',
		buttons: [
			{
				text: "Close", click: function() {
					$( this ).dialog( "close" );
				}
			}
		]
	});
	//==========================================================
	// Prepare the dialog that is shown while Snuffel connects
	// to a wifi network
	//==========================================================
	$( ".wifiConnectingDialog" ).dialog({
		title: 'Connecting...',
		buttons: [
			{
				text: "Cancel", click: function() {
					$(this).dialog('close');
				}
			}
		]
	});
});
