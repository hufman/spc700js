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
	this.cpu.load(instance, spcdata.subarray(0x25,0x2e));
	this.metadata.load(instance, spcdata.subarray(0x2e, 0xd4));
	this.ram.load(instance, spcdata.subarray(0x100, 0x10100));
	this.dsp.load(instance, spcdata.subarray(0x10100, 0x10180));
	this.metadata.load(instance, spcdata.subarray(0x10200, spcdata.length));
	
};
SPC700js.instance.prototype = {
	metadata:{
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
	},
	cpu:{
		PC:0,
		A:0,
		X:0,
		Y:0,
		SP:0,
		PSW:0,
		load:function(instance, data) {
			this.PC=data[0] | data[1]<<8;
			this.A=data[2];
			this.X=data[3];
			this.Y=data[4];
			this.PSW=data[5];
			this.SP=data[6];
			instance.disassembled.addAvailable(instance, this.PC);
		},
		setPSW:function(instance, PSWbit, value) {
			this.PSW=value ? this.PSW & ~(1<PSWbit) : this.PSW | (1<PSWbit);
		},
		tick:function(instance) {
			alert("Ticked CPU!");
		},
		push:function(instance, byteValue) {
			instance.ram.set(instance, this.SP, byteValue);
			this.SP--;
		},
		pop:function(instance) {
			this.SP--;
			return instance.ram.get(instance, this.SP);
		}
	},
	timers:{
		// The divisor between the 1mhz main cpu and incrementing each timer's internal counter
		privateDivisor:[
			128,
			128,
			16],
		// The progress of the private tickers until it increments the internal counter
		privateCounter:[
			0,
			0,
			0],
		// The internal divisor, at which the timer will increment the public counter
		// Represents Timer-X for each timer
		internalDivisor:[
			0,
			0,
			0],
		// The internal counter, which counts up until internalDivisor
		internalCounter:[
			0,
			0,
			0],
		// The public counter, which increments when internalCounter reaches internalDivisor
		counter:[
			0,
			0,
			0],
		counterMax:0x0f,
		
		// Whether the timer should increment at all
		timerEnabled:[
			0,
			0,
			0],
		
		tick:function(instance) {
			for (var i=0; i<2; i++) {
				this.privateCounter[i]++;
				if (this.timerEnabled[i] && this.privateCounter[i]==this.privateDivisor[i]) {
					this.privateCounter[i]=0;
					this.internalCounter[i]++;
				}
				if (this.internalCounter[i]==this.internalDivisor[i]) {
					this.internalCounter[i]=0;
					this.counter[i]++;
				}
				if (this.counter[i]==this.counterMax) {
					this.counter[i]=0;
				}
			}
		},
		
		enableTimer:function(instance, timer) {
			if (this.timerEnabled[timer])
				this.intenalCounter[timer]=0;
			this.timerEnabled[timer]=1;
		},
		disableTimer:function(instance, timer) {
			this.timerEnabled[timer]=0;
		},
		setTimer:function(instance, timer, value) {
			if (!this.timerEnabled[timer])
				this.internalCounter[timer]=0;
		},
		getCounter:function(instance, timer) {
			return this.counter[timer];
		}
	},
	io:{
		data:[],
		tick:function(instance) {
		},
		set:function(instance, location, value) {
			this.data[location]=value;
		},
		get:function(instance, location) {
			return this.data[location];
		}
	},
	dsp:{
		data:new Uint8Array(0x80),
		load:function(instance, data) {
			this.data=data;
		},
		tick:function(instance) {
		},
		set:function(instance, dspregister, value) {
		}
	},
	ram:{
		data:new Uint8Array(0xffff),
		load:function(instance, data) {
			this.data=data;
		},
		get:function(instance, location) {
			if (location==SPC700js.consts.CR)	// control register
				return 0;
				
			if (location>=SPC700js.consts.COUNTER_0 && location<=SPC700js.consts.COUNTER_2)	// timer counters
				return instance.timers.getCounter(instance, location-SPC700js.consts.COUNTER_0);
				
			if (location>=SPC700js.consts.IOPORT_0 && location <=SPC700js.consts.IOPORT_3)	// IO ports
				return instance.io.get(instance, location);
				
			if (location==SPC700js.consts.DSP_DATA)	// DSP data
				return instance.dsp.get(instance, this.ram.data[SPC700js.consts.DSP_ADDR]);
				
			return this.data[location];
		},
		set:function(instance, location, value) {
			if (location==SPC700js.consts.CR)	// control register
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
					instance.timers.enableTimer(instance, 2);
				else
					instance.timers.disableTimer(instance, 2);
					
				if (value & 1<<SPC700js.consts.CR_ST1)
					instance.timers.enableTimer(instance, 1);
				else
					instance.timers.disableTimer(instance, 1);
					
				if (value & 1<<SPC700js.consts.CR_ST0)
					instance.timers.enableTimer(instance, 0);
				else
					instance.timers.disableTimer(instance, 0);
			}
			
			if (location>=SPC700js.consts.TIMER_0 && location<=SPC700js.consts.TIMER_2)	// set timer value
				instance.timers.setTimer(instance, location-SPC700js.consts.TIMER_0, value);
				
			if (location==SPC700js.consts.DSP_DATA)	// dsp writes
				instance.dsp.set(instance, this.ram.data[SPC700js.consts.DSP_ADDR], value);
				
			if (location>=SPC700js.consts.IOPORT+0 && location <=SPC700js.consts.IOPORT_3)	// io ports
				instance.io.set(instance, location, value);
			this.data[location]=value;
			instance.disassembled.dirty(instance, location);
		}
	},
	disassembled:{
		map:{},
		available:[],
		targets:{},
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
	}
};
