var SPC700jsLoader = {
	loadFromUrl: function(url, onload, onfail) {
		var xhr = new XMLHttpRequest();
		xhr.open('GET', url, true);
		xhr.responseType = 'arraybuffer';
		xhr.onload = function(e) {
			if (this.status == 200) {
				var array = xhr.response;
				var data = new Uint8Array(array);

				onload(new SPC700js.instance(data));
			}
			else
			{
				onfail(this.status);
			}
		}
		xhr.send();
	}
}

if (!(Object.hasOwnProperty('keys'))) {
	Object.keys = function(obj) {
		var keys = [];
		for (var key in obj)
		{
			if (obj.hasOwnProperty(key))
				keys.push(key);
		}
		keys.sort();
		return keys;
	}
}

SPC700js={};
SPC700js.stringFromUint8=function(array, start, end) {
	var ret="";
	for (var i=start; i<end; i++) {
		if (array[i]==0)
			break;
		ret=ret+String.fromCharCode(array[i]);
	}
	return ret;
}
SPC700js.hexFromUint8=function(value) {
	var temp=value.toString(16);
	while (temp.length<2)
		temp="0"+temp;
	return "0x"+temp.toUpperCase();
}
SPC700js.hexFromUint16=function(value) {
	var temp=value.toString(16);
	while (temp.length<4)
		temp="0"+temp;
	return "0x"+temp.toUpperCase();
}
SPC700js.consts={
	// PSW bits, shift 1<<
	PSW_N:7,
	PSW_V:6,
	PSW_P:5,
	PSW_B:4,
	PSW_H:3,
	PSW_I:2,
	PSW_Z:1,
	PSW_C:0,

	// Control register bits, shift 1<<
	CR_PC32:5,
	CR_PC10:4,
	CR_ST2:2,
	CR_ST1:1,
	CR_ST0:0,

	// general addresses
	CR: 0xf1,
	DSP_ADDR: 0xf2,
	DSP_DATA: 0xf3,

	IOPORT_0:0xf4,
	IOPORT_1:0xf5,
	IOPORT_2:0xf6,
	IOPORT_3:0xf7,

	// timer addresses
	TIMER_0:0xfa,
	TIMER_1:0xfb,
	TIMER_2:0xfc,
	COUNTER_0:0xfd,
	COUNTER_1:0xfe,
	COUNTER_2:0xff
}
SPC700js.instance = function(spcdata) {
	var instance=this;

	this.events=new SPC700js.instance.events(instance);
	this.metadata=new SPC700js.instance.metadata(instance);
	this.cpu=new SPC700js.instance.cpu(instance);
	this.timers=new SPC700js.instance.timers(instance);
	this.io=new SPC700js.instance.io(instance);
	this.ram=new SPC700js.instance.ram(instance);
	this.dsp=new SPC700js.instance.dsp(instance);
	this.disassembled=new SPC700js.instance.disassembled(instance);

	if (typeof(spcdata)!='undefined') {
		this.cpu.load(instance, spcdata.subarray(0x25,0x2e));
		this.metadata.load(instance, spcdata.subarray(0x2e, 0xd4));
		this.ram.load(instance, spcdata.subarray(0x100, 0x10100));
		this.dsp.load(instance, spcdata.subarray(0x10100, 0x10180));
		this.metadata.load(instance, spcdata.subarray(0x10200, spcdata.length));
	}
};

/**
Responsible for broadcasting events from the playback engine to interested clients
*/
SPC700js.instance.events = function(){}
SPC700js.instance.events.prototype = {
	paused:false,
	listeners:{},
	registerListener:function(instance, key, callback) {
		if (!(this.listeners.hasOwnProperty(key))) {
			this.listeners[key]=[];
		}
		this.listeners[key].push(callback);

		var index=key.indexOf('.');
		if (index>0) {
			var sub=key.substr(0,index);
			if (instance.hasOwnProperty(sub) && 'initialSubscribe' in instance[sub]) {
				instance[sub].initialSubscribe(key, callback);
			}
		}
	},
	sendEvent:function(instance, key, data) {
		if (this.listeners.hasOwnProperty(key)) {
			if (!this.paused || this.pauseWhitelist.hasOwnProperty(key)) {
				var listeners=this.listeners[key];
				for (var i=0; i<listeners.length; i++) {
					listeners[i](data);
				}
			}
		}
	},
	pauseEvents:function(instance) {
		var modules = Object.keys(instance);
		for (var i = 0; i < modules.length; i++) {
			var module = instance[modules[i]];
			if (module == this) continue;
			if (module['pauseEvents']) {
				module.pauseEvents(instance)
			}
		}
		this.paused=true;
	},
	unpauseEvents:function(instance) {
		this.paused=false;
		var modules = Object.keys(instance);
		for (var i = 0; i < modules.length; i++) {
			var module = instance[modules[i]];
			if (module == this) continue;
			if (module['unpauseEvents']) {
				module.unpauseEvents(instance)
			}
		}
	}
}

/**
Contains metadata about the currently-loaded song, such as playback length, artist, and title
*/
SPC700js.instance.metadata = function(){}
SPC700js.instance.metadata.prototype = {
	data:{},
	load:function(instance, data) {
		if (data.length>4 && SPC700js.stringFromUint8(data, 0, 4)=="xid6")
			this.loadxid666(instance, data);
		else
			this.loadid666(instance, data);
	},
	loadxid666:function(instance, data) {
	},
	loadid666:function(instance, data) {
		this.data['title']=SPC700js.stringFromUint8(data, 0, 32);
		this.data['game']=SPC700js.stringFromUint8(data, 32, 64);
		this.data['dumper']=SPC700js.stringFromUint8(data, 64, 80);
		this.data['comments']=SPC700js.stringFromUint8(data, 80, 112);
		var textdate=SPC700js.stringFromUint8(data, 112, 123);
		if (textdate.length>0) {
			if (textdate[2]=='/' && textdate[5]=='/')
				this.data['dumpdate']=textdate;
			else
			{
				textdate==(data[112]<<24 | data[113]<<16 | data[114]<<8 | data[115])+'';
				this.data['dumpdate']=textdate.slice(4,6)+"/"+textdate.slice(6,8)+"/"+textdate.slice(0,4);
			}
		}
		this.data['playtime']=parseInt(SPC700js.stringFromUint8(data, 123, 126));
		this.data['fadems']=parseInt(SPC700js.stringFromUint8(data, 126, 131));
		this.data['artist']=SPC700js.stringFromUint8(data, 131, 163);
		this.data['channels']=data[163];
		this.data['emulator']=data[164]==0 ? 'Other' : data[164]==1 ? 'ZSNES' : 'Snes9x';
	}
};
/**
Executes the main CPU of the playback engine
*/
SPC700js.instance.cpu = function(){
	this.PC=0;
	this.A=0;
	this.X=0;
	this.Y=0;
	this.SP=0;
	this.PSW=0;
	this.subPC=0;
	this.curOpcode=null;
	this.pausedEvents = false;
	this.pausedStatus = {};
};
SPC700js.instance.cpu.prototype = {
	load:function(instance, data) {
		this.PC=data[0] | data[1]<<8;
		this.A=data[2];
		this.X=data[3];
		this.Y=data[4];
		this.PSW=data[5];
		this.SP=data[6];
		instance.disassembled.addAvailable(instance, this.PC);
	},
	initialSubscribe:function(event, callback) {
		var current={}
		var monitored=['PC','A','X','Y','SP','PSW'];
		for (var i=0; i<monitored.length; i++)
			current[monitored[i]] = this[monitored[i]];
		callback(current);
	},
	pauseEvents:function(instance) {
		this.pausedEvents = true;
		this.pausedStatus = {};
		var monitored=['PC','A','X','Y','SP','PSW'];
		for (var i=0; i<monitored.length; i++)
			this.pausedStatus[monitored[i]] = this[monitored[i]];
	},
	unpauseEvents:function(instance) {
		this.pausedEvents = false;
		var monitored=['PC','A','X','Y','SP','PSW'];
		var changed={};
		var old = this.pausedStatus;
		for (var i=0; i<monitored.length; i++) {
			if (old[monitored[i]] != this[monitored[i]]) {
				changed[monitored[i]] = this[monitored[i]];
			}
		}
		instance.events.sendEvent(instance, 'cpu.changed', changed);
	},
	setPSW:function(instance, PSWbit, value) {
		this.PSW=value ? this.PSW | (1<<PSWbit) : this.PSW & ~(1<<PSWbit);
	},
	getPSW:function(instance, PSWbit) {
		return (this.PSW & (1<<PSWbit)) > 0;
	},
	tick:function(instance) {
		var old = {};
		if (!instance.events.paused) {
			// save old state
			var monitored=['PC','A','X','Y','SP','PSW'];
			for (var i=0; i<monitored.length; i++)
				old[monitored[i]] = this[monitored[i]];
		}
		
			old['PC'] = this['PC'];
		if (this.curOpcode == null) {
			this.curOpcode = instance.disassembled.get(instance, this.PC).opcode;
		}
		SPC700js.opcodes[this.curOpcode].ucode[this.subPC](instance, this.PC);
		this.subPC++;

		if (!this.pausedEvents) {
			// notify listeners of changes
			var changed={};
			for (var i=0; i<monitored.length; i++) {
				if (old[monitored[i]] != this[monitored[i]]) {
					changed[monitored[i]] = this[monitored[i]];
				}
			}
			instance.events.sendEvent(instance, 'cpu.changed', changed);
		}

		if (old['PC'] != this.PC) {	// changed to a different opcode
			this.subPC = 0;
			this.curOpcode = instance.disassembled.get(instance, this.PC).opcode;
		}

		instance.dsp.tick(instance, 1);
		instance.timers.tick(instance, 1);
		instance.io.tick(instance, 1);
	},
	stepInstruction:function(instance) {
		var oldPC = this.PC;
		var opcode = instance.disassembled.get(instance, oldPC);
		var toRun = opcode.cycles-this.subPC;
		for (var i=0; i<toRun; i++) {
			this.tick(instance);
			if (oldPC != this.PC) break;	// moved to next instruction
		}
	},
	push:function(instance, byteValue) {
		instance.ram.set(instance, 0x100 + this.SP, byteValue);
		this.SP--;
		if (this.SP<0) this.SP+=256;
	},
	pop:function(instance) {
		this.SP++;
		if (this.SP>255) this.SP-=256;
		return instance.ram.get(instance, 0x100 + this.SP);
	}
};

SPC700js.instance.timers = function(){
	// The divisor between the 1mhz main cpu and incrementing each timer's internal counter
	this.privateDivisor=[
		128,
		128,
		16];
	// The progress of the private tickers until it increments the internal counter
	this.privateCounter=[
		0,
		0,
		0];
	// The internal divisor, at which the timer will increment the public counter
	// Represents Timer-X for each timer
	this.internalDivisor=[
		0,
		0,
		0];
	// The internal counter, which counts up until internalDivisor
	this.internalCounter=[
		0,
		0,
		0];
	// The public counter, which increments when internalCounter reaches internalDivisor
	this.counter=[
		0,
		0,
		0];
	this.counterMax=0x0f;
	
	// Whether the timer should increment at all
	this.timerEnabled=[
		0,
		0,
		0];
};
SPC700js.instance.timers.prototype = {
	tick:function(instance, count) {
		count = count || 1;
		for (var i=0; i<3; i++) {
			this.privateCounter[i]+=count;
			if (this.privateCounter[i]>=this.privateDivisor[i]) {
				this.privateCounter[i]-=this.privateDivisor[i];
				if (this.timerEnabled[i]) {
					this.internalCounter[i]++;
				}
			}
			if (this.internalCounter[i]>255)
				this.internalCounter[i]=0;

			if (this.internalCounter[i]>=this.internalDivisor[i]) {
				this.internalCounter[i]-=this.internalDivisor[i];
				this.counter[i]++;
			}
			if (this.counter[i]>this.counterMax) {
				this.counter[i]=0;
			}
		}
	},
	
	enableTimer:function(instance, timer) {
		if (this.timerEnabled[timer])
			this.internalCounter[timer]=0;
		this.timerEnabled[timer]=1;
	},
	disableTimer:function(instance, timer) {
		this.timerEnabled[timer]=0;
	},
	setTimer:function(instance, timer, value, loading) {
		if (!this.timerEnabled[timer] || loading)
			this.internalDivisor[timer]=value;
	},
	getCounter:function(instance, timer, viewonly) {
		var ret = this.counter[timer];
		if (!viewonly)
			this.counter[timer]=0;
		return ret;
	}
};
SPC700js.instance.io = function(){
	this.data=[0,0,0,0];
};
SPC700js.instance.io.prototype = {
	tick:function(instance) {
	},
	set:function(instance, location, value) {
		this.data[location]=value;
	},
	get:function(instance, location) {
		return this.data[location];
	}
};
SPC700js.instance.dsp = function(instance){
	this.data = new Uint8Array(0x80);
	this.pausedEvents = false;
	this.dirtyData = {};
};
SPC700js.instance.dsp.prototype = {
	load:function(instance, data) {
		this.data=data;
	},
	pauseEvents:function(instance) {
		this.pausedEvents = true;
		this.dirtyData = {};
	},
	unpauseEvents:function(instance) {
		this.pausedEvents = false;
		var addresses = Object.keys(this.dirtyData);
		for (var i = 0; i < addresses.length; i++) {
			var address = parseInt(addresses[i]);
			instance.events.sendEvent(instance, 'dsp.changed', {address:address, value:this.data[address]});
		}
	},
	tick:function(instance) {
	},
	get:function(instance, location) {
		return this.data[location & 0x7f];
	},
	set:function(instance, dspregister, value) {
		if (dspregister <= 0x7f) {
			this.data[dspregister]=value;
			instance.ram.dspChanged(instance, dspregister, value);
			if (!this.pausedEvents)
				instance.events.sendEvent(instance, 'dsp.changed', {address:dspregister, value:value});
			else
				this.dirtyData[dspregister] = value;
		}
	},
	setFromRam:function(instance, dspregister, value) {
		if (dspregister <= 0x7f) {
			this.data[dspregister]=value;
		}
	}
};
SPC700js.instance.ram = function() {
	this.data = new Uint8Array(0xffff);
	this.pausedEvents = false;
	this.dirtyData = {};
};
SPC700js.instance.ram.prototype = {
	load:function(instance, data) {
		this.data=data;
	},
	get:function(instance, location) {
		var retram = undefined;
		if (location>=SPC700js.consts.COUNTER_0 && location<=SPC700js.consts.COUNTER_2) { // timer counters
			retram = instance.timers.getCounter(instance, location-SPC700js.consts.COUNTER_0, viewonly);
		}
		else if (location>=SPC700js.consts.IOPORT_0 && location <=SPC700js.consts.IOPORT_3) {   // IO ports
			retram = instance.io.get(instance, location-SPC700js.consts.IOPORT_0);
		}
		else if (location==SPC700js.consts.DSP_DATA) {  // DSP data
			retram = instance.dsp.get(instance, this.data[SPC700js.consts.DSP_ADDR]);
		}
		else {
			retram = this.data[location];
		}
		return retram;
	},
	set:function(instance, location, value) {
		// set the ram data
		this.data[location]=value;
		instance.disassembled.dirty(instance, location);
		instance.events.sendEvent(instance, 'ram.changed', {address:location, value:value});
		if (!this.pausedEvents)
			instance.events.sendEvent(instance, 'ram.changed', {address:location, value:value});
		else
			this.dirtyData[location]=value;

		// set any special places too
		if (location==SPC700js.consts.CR)       // control register
		{
			if (value & 1<<SPC700js.consts.CR_PC32)
			{
				instance.io.set(instance, 0xf7, 0);
				instance.io.set(instance, 0xf6, 0);
			}
			if (value & 1<<SPC700js.consts.CR_PC10)
			{
				instance.io.set(instance, 0xf5, 0);
				instance.io.set(instance, 0xf4, 0);
			}
			if (value & 1<<SPC700js.consts.CR_ST2)
			{
				instance.timers.enableTimer(instance, 2);
			}
			else
			{
				instance.timers.disableTimer(instance, 2);
			}

			if (value & 1<<SPC700js.consts.CR_ST1)
			{
				instance.timers.enableTimer(instance, 1);
			}
			else
			{
				instance.timers.disableTimer(instance, 1);
			}

			if (value & 1<<SPC700js.consts.CR_ST0)
			{
				instance.timers.enableTimer(instance, 0);
			}
			else
			{
				instance.timers.disableTimer(instance, 0);
			}
		}

		if (location>=SPC700js.consts.TIMER_0 && location<=SPC700js.consts.TIMER_2)     // set timer value
		{
			instance.timers.setTimer(instance, location-SPC700js.consts.TIMER_0, value);
		}

		if (location==SPC700js.consts.DSP_DATA) // dsp writes
		{
			instance.dsp.setFromRam(instance, this.data[SPC700js.consts.DSP_ADDR], value);
		}

		if (location>=SPC700js.consts.IOPORT+0 && location <=SPC700js.consts.IOPORT_3)  // io ports
		{
			instance.io.set(instance, location, value);
		}

		// we changed the dsp addr, update the dsp data spot
		if (location==SPC700js.consts.DSP_ADDR) // dsp location
		{
			var dspvalue=instance.dsp.get(instance, value);
			this.data[SPC700js.consts.DSP_DATA]=dspvalue;
			instance.disassembled.dirty(instance, SPC700js.consts.DSP_DATA);
			if (!this.pausedEvents)
				instance.events.sendEvent(instance, 'ram.changed', {address:SPC700js.consts.DSP_DATA, value:dspvalue});
			else
				this.dirtyData[SPC700js.consts.DSP_DATA]=dspvalue;
		}

	},
	dspChanged:function(instance, dspregister, value) {
		if (this.get(instance, SPC700js.consts.DSP_ADDR) == dspregister) {
			this.data[SPC700js.consts.DSP_DATA]=value;
			instance.disassembled.dirty(instance, SPC700js.consts.DSP_DATA);
			if (!this.pausedEvents)
				instance.events.sendEvent(instance, 'ram.changed', {address:SPC700js.consts.DSP_DATA, value:value});
			else
				this.dirtyData[SPC700js.consts.DSP_DATA]=value;
		}
	},
	pauseEvents:function(instance) {
		this.pausedEvents = true;
		this.dirtyData = {};
	},
	unpauseEvents:function(instance) {
		this.pausedEvents = false;
		var addresses = Object.keys(this.dirtyData);
		for (var i = 0; i < addresses.length; i++) {
			var address = parseInt(addresses[i]);
			instance.events.sendEvent(instance, 'ram.changed', {address:address, value:this.data[address]});
		}
	}
};
SPC700js.instance.disassembled = function() {
	this.map={};
	this.available=[];
	this.targets={};
};
SPC700js.instance.disassembled.prototype = {
	addTarget:function(instance, srcLocation, dstLocation) {
		if (!( dstLocation in this.targets))
			this.targets[dstLocation]=[];
		if (!( srcLocation in this.targets[dstLocation]))
			this.targets[dstLocation].push(srcLocation);
		this.targets[dstLocation].sort();
	},
	getTarget:function(instance, dstLocation) {
		if (dstLocation in this.targets)
			return this.targets[dstLocation];
		return [];
	},
	addAvailable:function(instance, location) {
		if (!(location in this.available) && location)
			this.available.push(location);
	},
	parseNextAvailable:function(instance) {
		if (this.available.length>0) {
			var location=this.available.shift();
			this.get(instance, location);
			return true;
		}
		return false;
	},
	get:function(instance, location) {
		if (!(location in this.map)) {
			var opcodebyte=instance.ram.get(instance, location);
			var opcodehex=parseInt(opcodebyte).toString(16).toUpperCase();
			if (opcodehex.length==1) opcodehex="0"+opcodehex;
			var opcode=SPC700js.opcodes[opcodehex];
			this.map[location]=opcode;
			if (opcode.nextLocation)
			{
				this.addAvailable(instance, opcode.nextLocation(instance, location));
				this.addTarget(instance, location, opcode.nextLocation(instance, location));
			}
			if (opcode.branchTrueDest)
			{
				this.addAvailable(instance, opcode.branchTrueDest(instance, location));
				this.addTarget(instance, location, opcode.branchTrueDest(instance, location));
			}
			if (opcode.jumpDest)
			{
				this.addAvailable(instance, opcode.jumpDest(instance, location));
				this.addTarget(instance, location, opcode.jumpDest(instance, location));
			}
		}
		return this.map[location];
	},
	dirty:function(instance, location) {
		if (location in this.map) {
			delete this.map[location];
		}
	}
};
