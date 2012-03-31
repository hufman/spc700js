#!/usr/bin/python
""" Precompiler for SPC7000 opcodes
Reads in the spc700opcodes.txt table from stdin and generates a Javascript object containing the opcodes in the Javascript language

The table source is http://ekid.nintendev.com/snes/spctech.htm#cpuinstr
"""

from sys import stdin
import traceback

def jsonEncode(obj, nest=0):
	if isinstance(obj, basestring) and obj[0:8]=='function':
		#return '|<'+str+'>|'
		return obj
	if isinstance(obj, basestring):
		return '"' + obj + '"'
	if isinstance(obj, int) or isinstance(obj, long):
		return str(obj)
	if isinstance(obj, float):
		return "%.6f"%obj
	if isinstance(obj, bool):
		return 'True' if bool else 'False'
	if isinstance(obj, list) or isinstance(obj, tuple):
		return '[\n' + '    '*(nest+1) + (',\n'+'    '*(nest+1)).join([jsonEncode(x,nest+1) for x in obj]) + '\n' + '    '*nest + ']'
	if isinstance(obj, dict):
		return '{\n' + '    '*(nest+1) + (',\n'+'    '*(nest+1)).join(["%s: %s"%(jsonEncode(k,nest+1), jsonEncode(obj[k],nest+1)) for k in sorted(obj.keys())]) + '    '*nest + '\n' + '    '*nest + '}'
	if obj == None:
		return 'null'
	print("Failed to serialize %s"%obj)

opcodes={}

"""
Each opcode is broken down into two sets of micro-opcodes
The micro-opcodes indicate steps of the opcode that should run for each cpu tick

The GET micro-opcodes are implemented as TEMP=(micro-opcode expression), with the last result being stored into GET

The SET micro-opcodes are implemented as TEMP=(micro-opcode expression), with the final micro-opcode being expanded to plain javascript
"""
# Convert the GET half of the opcode to micro-opcodes
# These macros get expanded in the following definitions
commonMacros={
	'$TEMPADDR':'instance.cpu._tempaddr',
	'$TEMP':'instance.cpu._temp',
	'$GET':'instance.cpu._get',
	'$R8':'instance.ram.get(instance,instance.cpu._tempaddr)',
	'$R16HI':'(instance.ram.get(instance,instance.cpu._tempaddr) << 8)',
	'$R16LO':'instance.ram.get(instance,instance.cpu._tempaddr+1)',
	'$W8(':'instance.ram.set(instance,',
	'$PUSH(':'instance.cpu.push(instance,',
	'$POP(':'instance.cpu.pop(instance',
	'$DP':'((instance.cpu.PSW & SPC700js.consts.PSW_P) ? 0x0000 : 0x0100) + instance.ram.get(instance,location+$!ARG)',
	'$ABSHI':'(instance.ram.get(instance,location+$!ARG) << 8)',
	'$ABSLO':'instance.ram.get(instance,location+$!ARG)',
	'$IMM':'instance.ram.get(instance,location+$!ARG)',
	'$REL':'(instance.ram.get(instance,location+$~ARG) > 128 ? instance.ram.get(instance,location+$~ARG)-256 : instance.ram.get(instance,location+$!ARG))',
	'$N=(':'instance.cpu.setPSW(instance,SPC700js.consts.PSW_N, 0>',
	'$V=(':'instance.cpu.setPSW(instance,SPC700js.consts.PSW_V, 0xff<',
	'$Z=(':'instance.cpu.setPSW(instance,SPC700js.consts.PSW_Z, 0==',
	'$C=(':'instance.cpu.setPSW(instance,SPC700js.consts.PSW_C, 0xff<',
	'$N=':'instance.cpu.setPSW(instance,SPC700js.consts.PSW_N, ',
	'$V=':'instance.cpu.setPSW(instance,SPC700js.consts.PSW_V, ',
	'$P=':'instance.cpu.setPSW(instance,SPC700js.consts.PSW_P, ',
	'$H=':'instance.cpu.setPSW(instance,SPC700js.consts.PSW_H, ',
	'$I=':'instance.cpu.setPSW(instance,SPC700js.consts.PSW_I, ',
	'$C=':'instance.cpu.setPSW(instance,SPC700js.consts.PSW_C, ',
	'$H':'instance.cpu.getPSW(instance,SPC700js.consts.PSW_H)',
	'$A':'instance.cpu.A',
	'$X':'instance.cpu.X',
	'$Y':'instance.cpu.Y',
	'$PC':'instance.cpu.PC',
	'$SP':'instance.cpu.SP',
	'$PSW':'instance.cpu.PSW',
	'$H':'instance.cpu.getPSW(instance,SPC700js.consts.PSW_H)',
	'$Z':'instance.cpu.getPSW(instance,SPC700js.consts.PSW_Z)',
	'$C':'instance.cpu.getPSW(instance,SPC700js.consts.PSW_C)'
}
""" Used by sorted to sort the macros """
def sortMacros(macrokeys):
	return sorted(macrokeys, key=lambda key: chr(len(key)+32)+key, reverse=True)

#This is the micro-opcodes that are run to obtain the value to be acted on
""" Macros to help get stuff	
IMM gets the next 8 bits of the instruction
X/Y/A gets the associated CPU register
R8 gets 8 bits of RAM from the previously loaded address
R16 gets 16 bits of RAM from the previously loaded address
DP gets replaced with calls to get the current page address
ABS gets replaced with the 16-bit address in the instruction
# at the beginning means the step won't be processed for macros
"""
commonGetUcodes={
	'#imm':['$R8'],
	'(X)':['', '$R8'],
	'(Y)':['', '$R8'],
	'(X)+':['', '#instance.cpu.X++', '$R8'],
	'dp':['', '$R8'],
	'dpw':['', '$R16LO', '$R16HI+$TEMP'],
	'dp+X':['', '$R8'],
	'dp+Y':['', '$R8'],
	'!abs':['', '$R8'],
	'!abs+X':['', '$R8'],
	'!abs+Y':['', '$R8'],
	'[dp+X]':['', '$R8'],
	'[dp]+Y':['', '$R8'],
	'A':['$A'],
	'X':['$X'],
	'Y':['$Y'],
	'YA':['$Y<<8|$A'],
	'SP':['$SP']
}

# This contains definitions for displaying the address that a certain operation gets its source value from
commonAddressUcodes={
	'#imm':['location+$!ARG'],
	'(X)':['$X + (instance.cpu.PSW & SPC700js.consts.PSW_P) ? 0x0000 : 0x0100'],
	'(Y)':['$Y + (instance.cpu.PSW & SPC700js.consts.PSW_P) ? 0x0000 : 0x0100'],
	'(X)+':['$X + (instance.cpu.PSW & SPC700js.consts.PSW_P) ? 0x0000 : 0x0100'],
	'dp':['$DP'],
	'dpw':['$DP'],
	'dp+X':['$DP', '$TEMPADDR+$X'],
	'dp+Y':['$DP', '$TEMPADDR+$Y'],
	'!abs':['$ABSLO','$ABSHI+$TEMPADDR'],
	'!abs+X':['$ABSLO','$ABSHI+$TEMPADDR','$TEMPADDR+$X'],
	'!abs+Y':['$ABSLO','$ABSHI+$TEMPADDR','$TEMPADDR+$Y'],
	'[dp+X]':['$DP','$TEMPADDR+$X','$R16LO','$R16HI+$TEMPADDR'],
	'[dp]+Y':['$DP','$R16LO','$R16HI+$TEMPADDR','$TEMPADDR+$Y'],
	'A':['#A'],
	'X':['#X'],
	'Y':['#Y'],
	'YA':['#YA'],
	'SP':['#SP']
}

# This contains definitions for setting a value in the specified operand. The value is provided in $GET
commonSetUcodes={
	'A':['$A=$GET&0xff'],
	'X':['$X=$GET&0xff'],
	'Y':['$Y=$GET&0xff'],
	'YA':['$Y=($GET&0xff00)>>>8; $A=$GET&0xff'],
	'SP':['$SP=$GET&0xffff'],
	'(X)':['', '$W8($TEMPADDR, $GET)'],
	'(X)+':['', '$W8($TEMPADDR, $GET)'],
	'dp':['', '$W8($TEMPADDR, $GET)'],
	'dpw':['', '$W8($TEMPADDR, $GET&0xff00>>>8)', '$W8($TEMPADDR+1, $GET&0xff)'],
	'dp+X':['', '$W8($TEMPADDR, $GET)'],
	'dp+Y':['', '$W8($TEMPADDR, $GET)'],
	'!abs':['', '$W8($TEMPADDR, $GET)'],
	'!abs+X':['', '$W8($TEMPADDR, $GET)'],
	'!abs+Y':['', '$W8($TEMPADDR, $GET)'],
	'[dp+X]':['', '$W8($TEMPADDR, $GET)'],
	'[dp]+Y':['', '$W8($TEMPADDR, $GET)']
}

"""
Applies any macros in the list of strings
Returns a list of expanded strings
"""
def applyMacros(macros, realpre, prefix=""):
	jsout=[]
	if type(realpre)!=type(list()):
		prelist=[realpre]
	else:
		prelist=realpre
	for pre in prelist:
		#print("Adding %s to %s"%(prefix,pre))
		js=prefix+pre if len(pre)>0 else pre
		for key in sortMacros(macros.keys()):
			js=js.replace(key,macros[key])
		#print("Done setting to %s"%js)
		jsout.append(js)
	
	if type(realpre)!=type(list()):
		return jsout[0]
	else:
		return jsout

"""
Returns an copy of the string with all $!ARG macros replaced with the current argument count, incrementing arg[0] as well
"""
def applyArgMacro(realjs, arg):
	jsout=[]
	if type(realjs)!=type(list()):
		jslist=[realjs]
	else:
		jslist=realjs
	for js in jslist:
		while "$!ARG" in js or '$~ARG' in js:
			index1=js.find('$!ARG')
			index2=js.find('$~ARG')
			index1=index1 if index1>-1 else len(js)
			index2=index2 if index2>-1 else len(js)
			if index1<index2:
				js=js.replace("$!ARG", str(arg[0]), 1)
				arg[0]+=1
			elif index2<index1:
				js=js.replace("$~ARG", str(arg[0]), 1)
			else:
				print("Shouldn't happen!")
		jsout.append(js)
	
	if type(realjs)!=type(list()):
		return jsout[0]
	else:
		return jsout
	
def generateDisassembly(opname, args, opcode):
	earlypre={
		'mem,bit':'$TEMP=$ABSLO+$ABSHI'
	}
	pres={
		'#imm':'$IMM',
		'rel':'location+$REL+$~ARG',
		'bit':str(int(opcode[0],16)>>1),
		'bit3':'($TEMP>>>13)',
		'mem':'($TEMP&0x1FFF)',
		'/mem':'($TEMP&0x1FFF)',
		'(X)':'"(X)"',
		'(Y)':'"(Y)"',
		'(X)+':'"(X)+"',
		'dp':'$DP',
		'dpw':'$DP',
		'dp+X':'$DP',
		'dp+Y':'$DP',
		'!abs':'$ABSLO + $ABSHI',
		'!abs+X':'$ABSLO + $ABSHI',
		'!abs+Y':'$ABSLO + $ABSHI',
		'[!abs+X]':'$DP',
		'[dp+X]':'$DP',
		'[dp]+Y':'$DP',
		'C':'"C"',
		'A':'"A"',
		'X':'"X"',
		'Y':'"Y"',
		'YA':'"YA"',
		'SP':'"SP"',
		'PSW':'"PSW"',
		'upage':'$IMM',
		'n':opname[-1],
		'':''
	}
	
	formats={
		'#imm':'"#"+(%s).toString(16).toUpperCase()+"h"',
		'rel':'"0x"+(%s).toString(16).toUpperCase()',
		'bit':'%s',
		'bit3':'%s',
		'mem':'"0x"+(%s).toString(16).toUpperCase()',
		'/mem':'"~0x"+(%s).toString(16).toUpperCase()',
		'(X)':'%s',
		'(Y)':'%s',
		'(X)+':'%s',
		'dp':'"0x"+(%s).toString(16).toUpperCase()',
		'dpw':'"0x"+(%s).toString(16).toUpperCase()',
		'dp+X':'"0x"+(%s).toString(16).toUpperCase()+"+X"',
		'dp+Y':'"0x"+(%s).toString(16).toUpperCase()+"+Y"',
		'!abs':'"!0x"+(%s).toString(16).toUpperCase()',
		'!abs+X':'"!0x"+(%s).toString(16).toUpperCase()+"+X"',
		'!abs+Y':'"!0x"+(%s).toString(16).toUpperCase()+"+Y"',
		'[!abs+X]':'"[!0x"+(%s).toString(16).toUpperCase()+"+X]"',
		'[dp+X]':'"[0x"+(%s).toString(16).toUpperCase()+"+X]"',
		'[dp]+Y':'"[0x"+(%s).toString(16).toUpperCase()+"]+Y"',
		'C':'%s',
		'A':'%s',
		'X':'%s',
		'Y':'%s',
		'YA':'%s',
		'SP':'%s',
		'PSW':'%s',
		'upage':'"upage:"+%s',
		'n':'"%s"',
		'':'%s'
	}
	argNumber=[1]
	
	if len(args)==2 and args[0]=='dp' and (args[1]=='dp' or args[1]=='#imm'):
		swap=1
	else:
		swap=0
	
	earlyjs=""
	fullargs=','.join(args)
	for key in earlypre.keys():
		if key in fullargs:
			if len(earlyjs)>0:
				earlyjs=earlyjs+"; "
			earlyjs=earlyjs+earlypre[key]
	earlyjs=applyArgMacro(applyMacros(commonMacros, earlyjs), argNumber)
	if len(earlyjs)>0:
		earlyjs+="; "
	
	if 'mem,bit' in fullargs:
		args=[x.replace('bit','bit3') for x in args]
	
	preargs=args[:]
	for i in range(0, len(preargs)):
		preargs[i]=formats[preargs[i]] % pres[preargs[i]]
	jsargs=applyMacros(commonMacros, preargs)
	for i in range(0, len(jsargs)) :
		if swap:
			argNumber[0]=2-i
		jsargs[i]=applyArgMacro(jsargs[i], argNumber)
	if swap:
		argNumber[0]=+1
	output="var array=[ "+','.join(jsargs)+" ]; "
	return "function(instance, location) { "+earlyjs+output+'return "'+opname+'  "+array.join(); }'

"""
Combines all of the given information into an opcode object
The getUcodes are combined as above, where each step is added as $TEMP={microcode}
The last getUcode has an additional statement, $GET=$TEMP
Then, the modUcodes are processed. The last modUcode is merged into the beginning of the setUcodes
Then, the remaining modUcodes are added as individual steps, without adding any $TEMP to the beginning
Then, the setUcodes are added as individual steps, without adding any $TEMP to the beginning
If the last step of modUcodes ends with //, then the setUcodes will not be processed.
	This is used for CMP, where there isn't any memory change to write

The args array determine the parameters that get acted upon
If args has two elements, then the first element is used as the destination and the second is the source
If args has one element, then the first element is used as the source and a read of the destination is skipped
"""
def applyFromToMacros(macros, getUcodes, addressUcodes, modUcodes, setUcodes, args, opcode):

	opname=traceback.extract_stack()[-2][2]

	# Make sure that we didn't mess up
	if len(args)==1:
		fromarg=args[0]
		toarg=args[0]
	if len(args)==2:
		fromarg=args[1]
		toarg=args[0]
	if fromarg not in getUcodes:
		print("Can not decode %s get argument %s for opcode %s"%(opname, fromarg, opcode))
		return None
	if toarg not in setUcodes:
		print("Can not decode %s set argument %s for opcode %s"%(opname, toarg, opcode))
		return None
	if fromarg not in addressUcodes:
		print("Can not decode %s get address %s for opcode %s"%(opname, fromarg, opcode))
		return None
	if toarg not in addressUcodes:
		print("Can not decode %s set address %s for opcode %s"%(opname, toarg, opcode))
		return None
	if toarg not in modUcodes:
		print("Can not decode %s modification %s for opcode %s"%(opname, toarg, opcode))
		return None
		
	# swap args, if needed
	if len(args)==2 and args[0]=='dp' and (args[1]=='dp' or args[1]=='#imm'):
		swap=1
	else:
		swap=0
	
		
	# Get the FROM side of things
	realAddressArgs=[1]
	# Get the way to figure out the address to read from
	def expandAddressUcodes(addrpre,addressArgs,standalone):
		addrjs=[]
		for addr in addrpre:
			if len(addr)==0:
				addrjs.append('')
				continue
			if addr[0]=='#':
				# don't apply as part of the normal processing, because the later GET codes use it directory
				# However, it is useful for display purposes
				if standalone:
					addrjs.append('return "%s"'%addr[1:])
				else:
					addrjs.append('')
				continue
			js="$TEMPADDR="+addr if addr!=addrpre[-1] or not standalone else "return "+addr
			for key in sortMacros(macros.keys()):
				js=js.replace(key,macros[key])
			while "$!ARG" in js:
				js=js.replace("$!ARG", str(addressArgs[0]), 1)
				addressArgs[0]+=1
			addrjs.append(js)
		return addrjs

	# Expand the get ucodes
	def expandGetUcodes(frompre, addressArgs):
		fromjs=[]
		arg=1
		for pre in frompre:
			if len(pre)==0:
				fromjs.append('')
				continue
			if pre[0]=='#':
				fromjs.append(pre[1:])
				continue
			js="$TEMP="+pre
			for key in sortMacros(macros.keys()):
				js=js.replace(key,macros[key])
			while "$!ARG" in js:
				js=js.replace("$!ARG", str(addressArgs[0]), 1)
				addressArgs[0]+=1
			fromjs.append(js)
		return fromjs
	if swap:
		realAddressArgs[0]+=1
	fromaddrpre=addressUcodes[fromarg]
	fromaddrjs=expandAddressUcodes(fromaddrpre, realAddressArgs, False)
	frompre=getUcodes[fromarg]
	fromjs=expandGetUcodes(frompre, realAddressArgs)
	if frompre[0]!='':
		if fromaddrjs[-1]!='':
			fromaddrjs[-1] = fromaddrjs[-1] + "; "+fromjs[0]
		else:
			fromaddrjs[-1] = fromjs[0]
	fromjs.pop(0)
	fromjs=fromaddrjs+fromjs
	if swap:
		realAddressArgs[0]-=2

	# Get the javascript for getting the destination value
	readtoaddrpre=addressUcodes[toarg]
	readtoaddrjs=expandAddressUcodes(readtoaddrpre, [realAddressArgs[0]], False)
	readtopre=getUcodes[toarg]
	readtojs=expandGetUcodes(readtopre, [realAddressArgs[0]])
	readtojs=filter(lambda x: len(x)>0, readtoaddrjs+readtojs)


	# Get the TO side of things

	needsRead=False
	for pre in modUcodes[toarg]:
		needsRead = needsRead or '$DEST' in pre

	tojs=[]
	if len(args)==2:	# writing to a different place, load up the destination address
		pre=addressUcodes[toarg]
		js=expandAddressUcodes(addressUcodes[toarg], realAddressArgs, False)
		if len(js)==1 and js[0]=='':
			js.pop()
		tojs.extend(js)

	# Get the comands to read the original value from the TO side
	if needsRead:
		pre=getUcodes[toarg]
		js=expandGetUcodes(pre, realAddressArgs)
		if len(js)>1:
			js.insert(0, js.pop(0) + "; " + js.pop(0))
		elif len(tojs)>0:
			tojs[-1]=tojs[-1] + "; " + js.pop(0)
		tojs.extend(js)
		

	# Load up the modification
	modpre=modUcodes[toarg]
	modjs=[]
	for pre in modpre:
		js = pre
		for key in sortMacros(macros.keys()):
			js = js.replace(key,macros[key])
		if '$DEST' in js:
			js = js.replace('$DEST', 'instance.cpu._temp');
		modjs.append(js)
	
	# Apply any necessary destinations:
	if len(tojs)>0:
		if modjs[0]!='':
			tojs[-1] = tojs[-1] + "; " + modjs.pop(0)
		else:
			modjs.pop(0)
	tojs.extend(modjs)

	if tojs[-1][-2:] != '//':
		setpre = setUcodes[toarg]
		setjs=[]
		for pre in setpre:
			if len(pre)==0:
				setjs.append('')
				continue
			if pre[0]=='#':
				setjs.append(pre[1:])
				continue
			js="$TEMP=" + pre if pre != setpre[-1] else pre
			for key in sortMacros(macros.keys()):
				js=js.replace(key,macros[key])
			while "$!ARG" in js:
				js = js.replace("$!ARG", str(realAddressArgs[0]), 1)
				realAddressArgs[0]+=1
			setjs.append(js)
		if setjs[0] != '':
			if tojs[-1] != '':
				tojs[-1] = tojs[-1] + "; " + setjs.pop(0)
			else:
				tojs[-1]=setjs.pop(0)
		else:
			setjs.pop(0)
		tojs.extend(setjs)
	else:
		tojs[-1]=tojs[-1][:-2]

	if swap:
		realAddressArgs[0]+=1
	# Form into JSON
	obj={}
	
	# Add some extra functions
	addressArgs=[1]
	addrgjs=expandAddressUcodes(addressUcodes[fromarg], addressArgs, True)
	addrsjs=expandAddressUcodes(addressUcodes[toarg], addressArgs, True)
	
	obj['usedargs']=realAddressArgs[0]-1
	obj['readValue']="function(instance, location) {\nvar temp=0;\n" + ';\n'.join([js.replace('instance.cpu._temp','temp') for js in fromjs]) + "; return temp; }"
	obj['readOrigWriteValue']="function(instance, location) {\nvar temp=0;\n" + ';\n'.join([js.replace('instance.cpu._temp','temp') for js in readtojs]) + "; return temp; }"
	obj['readAddress']="function(instance, location) {\nvar temp=0;\n" + ';\n'.join([js.replace('instance.cpu._temp','temp') for js in addrgjs]) + ";}"
	obj['writeAddress']="function(instance, location) {\nvar temp=0;\n" + ';\n'.join([js.replace('instance.cpu._temp','temp') for js in addrsjs]) + ";}"
	obj['nextLocation']="function(instance, location) { return location+" + str(realAddressArgs[0]) + "; }"
	
	
	# Some final changes
	fromjs[-1]+="; instance.cpu._get=instance.cpu._temp"
	tojs[-1]+="; instance.cpu.PC=location+" + str(realAddressArgs[0])

	# Wrap in the final javascript functions
	obj['ucode']=[]
	for js in fromjs:
		obj['ucode'].append("function(instance, location) { %s; }"%js)
	for js in tojs:
		obj['ucode'].append("function(instance, location) { %s; }"%js)
	return obj;

def MOV(opname, args, opcode):
	# Convert the SET half of the opcode to micro-opcodes
	modUcodes={
		'A':['$N=($GET); $Z=($GET)'],
		'X':['$N=($GET); $Z=($GET)'],
		'Y':[''],
		'SP':[''],
		'(X)':['',''],
		'(X)+':['',''],
		'dp':['',''],
		'dp+X':['',''],
		'dp+Y':['',''],
		'!abs':['',''],
		'!abs+X':['',''],
		'!abs+Y':['',''],
		'[dp+X]':['',''],
		'[dp]+Y':['','']
	}
	
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);
	
def ADC(opname, args, opcode):
	# Convert the SET half of the opcode to micro-opcodes
	mod='$H= ($GET&0x0f)+($DEST&0x0f)>9); $GET=$DEST+$GET+$C; $N=($GET); $V=($GET); $Z=($GET); $C=($GET)'
	modUcodes={
		'A':[mod],
		'(X)':[mod],
		'dp':['', mod]
	}
	
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);
	
def SBC(opname, args, opcode):
	# Convert the SET half of the opcode to micro-opcodes
	mod='$H= $DEST&0x0f < $GET&0x0f); var newC=$DEST<$GET; $GET=$DEST-$GET+1-$C; $N=($GET); $V=newC); $Z=($GET); $C=newC)'
	modUcodes={
		'A':[mod],
		'(X)':[mod],
		'dp':['', mod]
	}
	
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);
	
def CMP(opname, args, opcode):
	# Convert the SET half of the opcode to micro-opcodes
	flags='$N=($GET); $V=$DEST<$GET); $C=$DEST<$GET); $H= $DEST&0x0f < $GET&0x0f); $Z=($GET)//'
	modUcodes={
		'A':['$GET=$DEST-$GET; ' + flags],
		'X':['$GET=$DEST-$GET; ' + flags],
		'Y':['$GET=$DEST-$GET; ' + flags],
		'(X)':['$GET=$DEST-$GET', flags],
		'dp':['', '$GET=$DEST-$GET', flags]
	}
	
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def AND(opname, args, opcode):
	# Convert the SET half of the opcode to micro-opcodes
	mod='$GET=$DEST & $GET; $N=($GET); $Z=($GET)'
	modUcodes={
		'A':[mod],
		'(X)':[mod],
		'dp':['', mod]
	}
	
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);
	
def OR(opname, args, opcode):
	# Convert the SET half of the opcode to micro-opcodes
	mod='$GET=$DEST | $GET; $N=($GET); $Z=($GET)'
	modUcodes={
		'A':[mod],
		'(X)':[mod],
		'dp':['', mod]
	}
	
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def EOR(opname, args, opcode):
	# Convert the SET half of the opcode to micro-opcodes
	mod='$GET=$DEST ^ $GET; $N=($GET); $Z=($GET)'
	modUcodes={
		'A':[mod],
		'(X)':[mod],
		'dp':['', mod]
	}
	
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def INC(opname, args, opcode):
	# Convert the SET half of the opcode to micro-opcodes
	mod='$GET=$GET+1; $N=($GET); $Z=($GET)'
	modUcodes={
		'A':[mod],
		'dp':[mod],
		'dp+X':[mod],
		'!abs':[mod],
		'X':[mod],
		'Y':[mod]
	}
	
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def DEC(opname, args, opcode):
	# Convert the SET half of the opcode to micro-opcodes
	mod='$GET=$GET-1; $N=($GET); $Z=($GET)'
	modUcodes={
		'A':[mod],
		'dp':[mod],
		'dp+X':[mod],
		'!abs':[mod],
		'X':[mod],
		'Y':[mod]
	}
	
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);
	
def ASL(opname, args, opcode):
	# Convert the SET half of the opcode to micro-opcodes
	mod='$GET=$GET<<1; $C=($GET); $N=($GET); $Z=($GET)'
	modUcodes={
		'A':[mod],
		'dp':[mod],
		'dp+X':[mod],
		'!abs':[mod]
	}
	
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);
	
def LSR(opname, args, opcode):
	# Convert the SET half of the opcode to micro-opcodes
	mod='$C=$GET&1); $GET=$GET>>>1; $N=($GET); $Z=($GET)'
	modUcodes={
		'A':[mod],
		'dp':[mod],
		'dp+X':[mod],
		'!abs':[mod]
	}
	
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);
	
def ROL(opname, args, opcode):
	# Convert the SET half of the opcode to micro-opcodes
	mod='$GET=$GET<<1; $GET=$GET+$C; $C=($GET); $N=($GET); $Z=($GET)'
	modUcodes={
		'A':[mod],
		'dp':[mod],
		'dp+X':[mod],
		'!abs':[mod]
	}
	
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def ROR(opname, args, opcode):
	# Convert the SET half of the opcode to micro-opcodes
	mod='$TEMP=$C; $C=$GET&1); $GET=$GET>>>1; $GET=$GET+$TEMP<<7; $N=($GET); $Z=($GET)'
	modUcodes={
		'A':[mod],
		'dp':[mod],
		'dp+X':[mod],
		'!abs':[mod]
	}
	
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def XCN(opname, args, opcode):
	mod=['$TEMP=$TEMP<<4', '', '', '$TEMP=($TEMP & 0xf0) | (($TEMP&0x0f00)>>>8)']
	modUcodes={'A':mod}
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def MOVW(opname, args, opcodes):
	args=[arg.replace('dp','dpw') for arg in args]
	modUcodes={
		'dpw':['$N=($GET); $Z=($GET)'],
		'YA':['', '']
	}
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def INCW(opname, args, opcodes):
	args=[arg.replace('dp','dpw') for arg in args]
	modUcodes={
		'dpw':['$GET=$GET+1; $N=($GET); $Z=($GET)']
	}
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def DECW(opname, args, opcodes):
	args=[arg.replace('dp','dpw') for arg in args]
	modUcodes={
		'dpw':['$GET=$GET-1; $N=($GET); $Z=($GET)']
	}
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def ADDW(opname, args, opcodes):
	args=[arg.replace('dp','dpw') for arg in args]
	modUcodes={
		'YA':['$H= ($GET&0x0f)+($DEST&0x0f)>9)', '$GET=$GET+$DEST; $N=($GET); $V= $GET>0xffff); $Z=($GET); $C= $GET>0xffff)']
	}
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def SUBW(opname, args, opcodes):
	args=[arg.replace('dp','dpw') for arg in args]
	modUcodes={
		'YA':['$V=$DEST<$GET); $C=$DEST<$GET); $H= $DEST&0x0f < $GET&0x0f)', '$GET=$DEST-$GET; $N=($GET); $Z=($GET)']
	}
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def CMPW(opname, args, opcodes):
	args=[arg.replace('dp','dpw') for arg in args]
	modUcodes={
		'YA':['$C=$DEST<$GET); $H= ($DEST&0x0f < $GET&0x0f)); $GET=$DEST-$GET; $N=($GET); $Z=($GET) //']
	}
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def MUL(opname, args, opcode):
	modUcodes={
		'YA':['', '', '', '', '$TEMP=($GET&0xff00)', '$TEMP=$GET>>>8', '$TEMP=$TEMP*($GET&0xff)', '']
	}
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def DIV(opname, args, opcode):
	modUcodes={
		'YA':['', '', '$TEMP=$YA', '', '', '$Y=$TEMP % $GET', '', '', '$A=Math.floor($TEMP / $GET)', '', '//']
	}
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def DAA(opname, args, opcode):
	modUcodes={
		'A':['if(($A & 0x0f) > 9 || $H) {$A=$A+6; $H=1)}', 'if(($A & 0xff) > 0x9f || $C) {$A=$A+0x60; $C=1)}']   # roll over the BCD low nibble to increase the high nibble
	}
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def DAS(opname, args, opcode):
	modUcodes={
		'A':['if(($A & 0x0f) > 9 || $H) {$A=$A-6; $H=1)}', 'if(($A & 0xff) > 0x9f || $C) {$A=$A-0x60; $C=1)}']   # roll over the BCD low nibble to increase the high nibble
	}
	return applyFromToMacros(commonMacros, commonGetUcodes, commonAddressUcodes, modUcodes, commonSetUcodes, args, opcode);

def BRANCH(opname, args, opcode):
	opname='CBNEX' if opcode == 'DE' else opname
	opname='DBNZY' if opcode == 'FE' else opname
	
	tests = {
		'BRA':['$TEMPADDR="TRUE"', 'true'],
		'BEQ':['$TEMPADDR="Z"', '$Z ==1'],
		'BNE':['$TEMPADDR="Z"', '$Z ==0'],
		'BCS':['$TEMPADDR="C"', '$C ==1'],
		'BCC':['$TEMPADDR="C"', '$C ==0'],
		'BVS':['$TEMPADDR="V"', '$V ==1'],
		'BVC':['$TEMPADDR="V"', '$V ==0'],
		'BMI':['$TEMPADDR="N"', '$N ==1'],
		'BPL':['$TEMPADDR="N"', '$N ==0'],
		'BBS':['', '$TEMPADDR=$DP', '$TEMP=$R8', '$TEMP & (1<<$BIT)', '$TEMP>0'],
		'BBC':['', '$TEMPADDR=$DP', '$TEMP=$R8', '$TEMP & (1<<$BIT)', '$TEMP==0'],
		'CBNE':['', '$TEMPADDR=$DP', '$TEMP=$R8', '', '$TEMP!=$a'],
		'CBNEX':['', '$TEMPADDR=$DP', '$TEMPADDR=$TEMPADDR+$X', '$TEMP=$R8', '', '$TEMP!=$a'],
		'DBNZ':['$TEMPADDR=$DP', '$TEMP=$R8', '$TEMP=$TEMP-1', '$W8($TEMPADDR, $TEMP)', '$TEMP==0'],
		'DBNZY':['$TEMP=$Y', '$TEMP=$TEMP-1', '$Y=$TEMP', '$TEMP==0']
	}
	
	bit=str(int(opcode[0],16)>>1)
	myMacros=dict(commonMacros)
	myMacros['$BIT']=str(bit)

	obj={}

	addressArgs=[1]
	fulljs = applyArgMacro(applyMacros(myMacros, tests[opname]), addressArgs)
	addrjs = filter(lambda x: myMacros['$TEMPADDR']+"=" in x, fulljs)
	
	setAddressArgs=[addressArgs[0]]
	setpre = ['$TEMP=$IMM; if ($TEMP>127) $TEMP=$TEMP-256', 'location+$TEMP+$~ARG']
	setjs=applyArgMacro(applyMacros(myMacros, setpre), addressArgs)
	
	obj['testResult']='function(instance, location) {\n' + ';\n'.join(filter(lambda x: len(x.strip())>0, fulljs[:-1])) + (';\n' if len(filter(lambda x: len(x.strip())>0, fulljs))>1 else '') + 'return %s; }'%fulljs[-1]
	
	fulljs[-1] = 'if (!(%s)) instance.cpu.PC=location+%d' %(fulljs[-1], setAddressArgs[0])
	
	obj['usedargs']=addressArgs[0]-1
	obj['branchTrueDest']='function(instance, location) {\n' + ';\n'.join([js.replace('instance.cpu._temp','temp') for js in setjs[:-1]]) + ';\nreturn '+setjs[-1].replace('instance.cpu._temp','temp') + "; }"
	obj['nextLocation']='function(instance, location) { return location+%d'%addressArgs[0]+"; }"
	obj['readAddress']='function(instance, location) { var tempaddr=""; ' + '; '.join([js.replace('instance.cpu._tempaddr', 'tempaddr') for js in addrjs]) + '; return tempaddr; }'
	
	obj['ucode']=[]
	obj['ucode'].extend(["function(instance, location) { %s; }"%js for js in fulljs])
	obj['ucode'].extend(["function(instance, location) { %s; }"%js for js in setjs[:-1]])
	obj['ucode'].append("function(instance, location) { instance.cpu.location=%s; }"%setjs[-1])
	return obj
BRA=BEQ=BNE=BCS=BCC=BVS=BVC=BMI=BPL=BBS=BBC=CBNE=DBNZ=BRANCH

def JMP(opname, args, opcode):
	addrpres={
		'5F':commonAddressUcodes['!abs'],
		'1F':commonAddressUcodes['!abs+X']+['', '$R8']
	}
	
	addressArg=[1]
	addrjs=applyArgMacro(applyMacros(commonMacros, addrpres[opcode], "$TEMPADDR="), addressArg)
	
	singleaddrjs = filter(lambda x: len(x)>0, addrjs)
	singleaddrjs = [js.replace('instance.cpu._tempaddr', 'tempaddr') for js in singleaddrjs]
	
	obj={}
	obj['jumpDest'] = 'function(instance, location) { var tempaddr; ' + '; '.join(singleaddrjs) + "; return tempaddr; }"
	obj['usedargs']=addressArg[0]-1
	obj['nextLocation']=obj['jumpDest']
	obj['ucode'] = ["function(instance, location) { %s; }" % js for js in addrjs]
	obj['ucode'].append('function(instance, location) { instance.cpu.PC=instance.cpu._tempaddr; }')
	return obj

def CALL(opname, args, opcode):
	faffing={
		'CALL':2, 'PCALL':1, 'TCALL':3
	}
	
	getpres={
		'!abs':commonAddressUcodes['!abs'],
		'upage':['location+$!ARG; $R8'],
		'n':['0']
	}
	
	setpres=[
		'$TEMP=$PC+$!ARG', '$PUSH($TEMP&0ff00 >>> 8)', '$PUSH($TEMP&0ff)',
		'$PC=$TEMPADDR'
	]
	
	getjs=['']*faffing[opname]
	
	argCount=[1]
	getjs=getjs+applyArgMacro(applyMacros(commonMacros, getpres[args[0]], "$TEMPADDR="), argCount)
	
	setjs=applyArgMacro(applyMacros(commonMacros, setpres), [argCount[0]])
	
	obj={}
	obj['usedargs']=argCount[0]-1
	obj['callAddress']='function(instance, location) { var tempaddr=0; ' + '; '.join(filter(lambda x: len(x)>0, [js.replace('instance.cpu._temp', 'temp') for js in getjs])) + '; return tempaddr; }'
	obj['nextLocation']=obj['callAddress']
	obj['ucode']=getjs+setjs
	return obj
PCALL=TCALL=CALL

def BRK(opname, args, opcode):
	obj={}
	obj['usedargs']=0
	obj['nextLocation']='function(instance, location) { return location+1; }';
	obj['ucode']=['function(instance, location) { }']*6
	obj['ucode'].append('function(instance, location) { instance.cpu.setPSW(instance.consts.PSW_B); }');
	obj['ucode'].append('function(instance, location) { instance.cpu.clearPSW(instance.consts.PSW_I); instance.cpu.PC=instance.cpu.PC+1}');
	return obj

def RET(opname, args, opcode):
	getpre=[
		'$TEMPADDR=$POP()',
		'$TEMPADDR=$TEMPADDR+$POP()<<8']
	if opname=='RETI':
		getpre.append('$PSW=$POP()')
	setpre=[
		'', '',
		'$PC=$TEMPADDR']
	
	getjs=applyMacros(commonMacros,getpre)
	setjs=applyMacros(commonMacros,setpre)

	obj={}
	obj['usedargs']=0
	obj['returnAddress']='function(instance, location) { var tempaddr=0; ' + '; '.join(filter(lambda x: len(x)>0, [js.replace('instance.cpu._temp', 'temp') for js in getjs])) + '; }'
	obj['nextLocation']=obj['returnAddress']
	obj['ucode']=['function(instance, location) { %s; }'%js for js in getjs+setjs]
	return obj
RETI=RET

def PUSH(opname, args, opcode):
	getjs=['instance.cpu._temp='+commonMacros['$'+args[0]]]
	setjs=['', '', 'instance.cpu.push(instance.cpu._temp)']

	obj={}
	obj['usedargs']=0
	obj['nextLocation']='function(instance, location) { return location+1; }'
	obj['ucode']=['function(instance, location) { %s; }'%js for js in getjs+setjs]
	return obj
	
def POP(opname, args, opcode):
	getjs=['instance.cpu._temp=instance.cpu.pop()']
	setjs=['', '', commonMacros['$'+args[0]]+'=instance.cpu._temp']

	obj={}
	obj['usedargs']=0
	obj['nextLocation']='function(instance, location) { return location+1; }'
	obj['ucode']=['function(instance, location) { %s; }'%js for js in getjs+setjs]
	return obj
	
def SET1(opname, args, opcode):
	bit=str(int(opcode[0],16)>>1)
	getpre=['$TEMPADDR=$DP', '$TEMP=$R8']
	modpres={
		'SET1':['$TEMP=$TEMP & (1<<$BIT)'],
		'CLR1':['$TEMP=$TEMP & (0xff ^ (1<<$BIT))'],
	}
	setpre=['$W8($TEMPADDR,$TEMP)']
	
	mymacros=dict(commonMacros)
	mymacros['$BIT']=str(bit)
	
	arg=[1]
	
	obj={}
	obj['ucode']=['function(instance, location) { %s; }'%applyArgMacro(applyMacros(mymacros,x),arg) for x in getpre+modpres[opname]+setpre]
	obj['readValue']='function(instance, location) { var temp=0; var tempaddr=0; ' + '; '.join([applyArgMacro(applyMacros(mymacros,x),[1]).replace('instance.cpu.temp', 'temp') for x in getpre]) + '; return temp; }'
	obj['readOrigWriteValue']=obj['readValue']
	obj['readAddress']='function(instance, location) { var tempaddr=0; ' + applyArgMacro(applyMacros(mymacros,getpre[0]),[1]).replace('instance.cpu.temp', 'temp') + '; return tempaddr; }'
	obj['writeAddress']=obj['readAddress']
	obj['nextLocation']='function(instance, location) { return location + %s; }'%arg[0]
	obj['usedargs']=arg[0]-1
	return obj
CLR1=SET1

def TSET1(opname, args, opcode):
	getpre=['$TEMPADDR=$ABSLO', '$TEMPADDR=$TEMPADDR+$ABSHI', '$TEMP=$R8']
	arg=[1]
	
	modpres={
		'TSET1':['$TEMP=$TEMP & $A'],
		'TCLR1':['$TEMP=$TEMP & (~$A)']
	}
	getjs=applyArgMacro(applyMacros(commonMacros, getpre+modpres[opname]),arg)
	
	setpre=['$N=($TEMP); $Z=($TEMP)', '$W8($TEMPADDR, $TEMP); $PC=location+'+str(arg[0])]
	setjs=applyArgMacro(applyMacros(commonMacros, setpre),arg)
	
	obj={}
	obj['ucode']=['function(instance, location) { %s; }'%x for x in getjs+setjs]
	
	obj['readValue']='function(instance, location) { var temp=0; var tempaddr=0; ' + '; '.join([x.replace('instance.cpu.temp', 'temp') for x in getjs[:-1]]) + '; return temp; }'
	obj['readOrigWriteValue']=obj['readValue']
	obj['readAddress']='function(instance, location) { var tempaddr=0; ' + '; '.join([x.replace('instance.cpu.temp', 'temp') for x in getjs[:-2]]) + ' ; return tempaddr; }'
	obj['writeAddress']=obj['readAddress']
	obj['nextLocation']='function(instance, location) { return location + %s; }'%arg[0]
	obj['usedargs']=arg[0]-1
	
	return obj
TCLR1=TSET1

def BIT1(opname, args, opcode):
	if '/' in args[1]:
		opname=opname+'~'
	if args[2]=='C':
		opname=opname+'C'
	
	addrpre=['$TEMP=$ABSLO', '$TEMP=$TEMP+$ABSHI']
	getpre=['var bit=$TEMP>>>13; $TEMPADDR=$TEMP&0x1FFF']
	if opname!='MOV1C':
		getpre[0]+='; $TEMP=($R8 && 1<<bit)>>>bit'
	faff={
		'AND1':[],
		'AND1~':[],
		'OR1':[''],
		'OR1~':[''],
		'EOR1':[''],
		'MOV1':[],
		'MOV1C':['','']
	}
	arg=[1]
	getjs=[applyArgMacro(applyMacros(commonMacros,x),arg) for x in addrpre+getpre+faff[opname]]
	setpres={
		'AND1':['$C=$C & $TEMP)'],
		'AND1~':['$C=$C & ~$TEMP)'],
		'OR1':['$C=$C | $TEMP)'],
		'OR1~':['$C=$C | ~$TEMP)'],
		'EOR1':['$C=$C ^ $TEMP)'],
		'MOV1':['$C=$TEMP)'],
		'MOV1C':['var bit=$TEMP>>>13; $W8($TEMPADDR, $C ? $R8 | ($C<<bit) : $R8 & ~($C<<bit))']
	}
	setpre=setpres[opname]
	setpre[-1]=setpre[-1]+'; $PC=location+'+str(arg[0])
	setjs=[applyMacros(commonMacros,x) for x in setpre]
	
	obj={}
	obj['ucode']=['function(instance, location) { %s; }'%x for x in getjs+setjs]
	obj['nextLocation']='function(instance, location) { return location+'+str(arg[0])+'; }'
	obj['readAddress']='function(instance, location) { var temp=0; var tempaddr=0; '+'; '.join([applyArgMacro(applyMacros(commonMacros,x),[1]).replace('instance.cpu._temp','temp') for x in addrpre+getpre]) + '; return tempaddr; }'
	obj['readValue']='function(instance, location) { var temp=0; var tempaddr=0; '+'; '.join([applyArgMacro(applyMacros(commonMacros,x),[1]).replace('instance.cpu._temp','temp') for x in addrpre+getpre]) + '; return temp; }'
	obj['readOrigWriteValue']='function(instance, location) { return $C; }'
	obj['writeAddress']='function(instance, location) { return "C"; }'
	obj['usedargs']=arg[0]-1
	if args[2]=='C':	# copying C to memory
		obj['readOrigWriteValue']='function(instance, location) { var temp=0; var tempaddr=0; '+'; '.join([applyArgMacro(applyMacros(commonMacros,x),[1]).replace('instance.cpu._temp','temp') for x in addrpre+getpre]) + '; return instance.ram.get(instance,tempaddr); }'
		obj['readValue']='function(instance, location) { var temp=0; var tempaddr=0; ' + '; '.join([applyArgMacro(applyMacros(commonMacros,x),[1]).replace('instance.cpu._temp','temp') for x in addrpre+['var bit=$TEMP>>>13','return $C + "<<"+bit']]) + '; }'
		obj['writeAddress']=obj['readAddress']
	return obj
AND1=OR1=EOR1=MOV1=BIT1

def NOT1(opname, args, opcode):
	addrpre=['$TEMP=$ABSLO', '$TEMP=$TEMP+$ABSHI', '$TEMPADDR=$TEMP&0x1FFF']
	getpre=['var bit=$TEMP>>>13; $TEMP=$R8; $TEMP=($TEMP & 1<<bit) ? $TEMP & ~(1<<bit) : $TEMP | (1<<bit)']
	setpre=['$W8($TEMPADDR, $TEMP)']
	arg=[1]
	addrjs=applyArgMacro(applyMacros(commonMacros,addrpre),arg)
	getjs=applyMacros(commonMacros,getpre)
	setjs=applyMacros(commonMacros,setpre)
	setjs[-1]=setjs[-1]+'; instance.cpu.PC=location+'+str(arg[0])

	obj={}
	obj['ucode']=['function(instance, location) { %s; }'%x for x in addrjs+getjs+setjs]
	obj['nextLocation']='function(instance, location) { return location + ' + str(arg[0]) + '; }'
	obj['readAddress']='function(instance, location) { ' + '; '.join([x.replace('instance.cpu._temp', 'temp') for x in addrjs]) + '; return tempaddr; }'
	obj['readValue']='function(instance, location) { ' + '; '.join([x.replace('instance.cpu._temp', 'temp') for x in addrjs+getjs]) + '; return temp; }'
	obj['writeAddress']=obj['readAddress']
	obj['readOrigWriteValue']=obj['readValue']
	obj['usedargs']=arg[0]-1
	return obj

def PSW(opname, args, opcode):
	addrpre={
		'CLRC':'C',
		'SETC':'C',
		'NOTC':'C',
		'CLRV':'V',
		'CLRP':'P',
		'SETP':'P',
		'EI':'I',
		'DI':'I'
	}

	modpre={
		'CLRC':'$C=0)',
		'SETC':'$C=1)',
		'NOTC':'$C=~$C)',
		'CLRV':'$V=0); $H=0)',
		'CLRP':'$P=0)',
		'SETP':'$P=1)',
		'EI':'$I=1)',
		'DI':'$I=0)'
	}
	faff={
		'CLRC':1,
		'SETC':1,
		'NOTC':2,
		'CLRV':1,
		'CLRP':1,
		'SETP':1,
		'EI':2,
		'DI':2
	}
	modjs=[applyMacros(commonMacros,modpre[opname])]
	faffjs=['']*faff[opname]
	faffjs[-1]='instance.cpu.PC=location+1'

	obj={}
	obj['ucode']=['function(instance, location) { %s; }'%x for x in modjs+faffjs]
	obj['nextLocation']='function(instance, location) { return location + 1; }'
	obj['readAddress']='function(instance, location) { return "'+addrpre[opname]+'"; }'
	obj['readValue']='function(instance, location) { return instance.cpu.getPSW(SPC700js.consts.PSW_'+addrpre[opname]+'); }'
	obj['writeAddress']=obj['readAddress']
	obj['readOrigWriteValue']=obj['readValue']
	obj['usedargs']=0
	return obj
CLRC=SETC=NOTC=CLRV=CLRP=SETP=EI=DI=PSW

def NOP(opname, args, opcode):
	obj={}
	obj['ucode']=['function(instance, location){}'] * (2 if opname=='NOP' else 3)
	if opname!='STOP':
		obj['ucode'][-1]='function(instance, location) { instance.cpu.PC=location+1; }'
	obj['nextLocation']='function(instance, location) { return location+1; }'
	obj['usedargs']=0
	return obj
SLEEP=STOP=NOP
	
for line in stdin:
	if len(line.strip())<3:
		continue
	
	if line[0]=='#':
		continue
	
	name=line[0:8].strip()
	args=line[8:22].strip()
	opcode=line[22:24].strip()
	bytes=line[32:36].strip()
	bytes=int(bytes) if len(bytes)>0 else 0
	cycles=line[40:46].strip().split('/')[-1]
	cycles=int(cycles) if len(cycles)>0 else 0
	flags=line[48:56].strip()
	comments=line[58:].strip()
	
	argsplit=[arg.strip() for arg in args.split(',')]

	if len(name)<1:
		continue
	
	def fleshout(obj):
		obj['bytes']=bytes
		obj['cycles']=cycles
		obj['desc']="%s  %s"%(name, args)
		obj['disassembly']=generateDisassembly(name, argsplit, obj['opcode']);
		if len(obj['ucode'])!=cycles:
			print("Incorrect cycle count for opcode %s: "%opcode)
		if obj['usedargs']!=bytes-1:
			print("Incorrect byte count for opcode %s: "%opcode)
		del obj['usedargs']

	if name in globals():
		if opcode[0]=='n':
			output=[]
			for bit in range(0, 16, 2):
				curopcode="%X%s"%(bit,opcode[1])
				output=globals()[name](name,argsplit,curopcode)
				output['opcode']=curopcode
				fleshout(output)
				output['desc']=output['desc'][:3]+str(bit/2+1)+output['desc'][4:]
				if curopcode in opcodes:
					print("Duplicate opcode: "+curopcode)
				opcodes[curopcode]=output
		elif opcode[0]=='x':
			output=[]
			for bit in range(0, 16, 2):
				curopcode="%X%s"%(bit,opcode[1])
				output=globals()[name](name,argsplit,curopcode)
				output['opcode']=curopcode
				fleshout(output)
				output['desc']=output['desc'][:3]+str(bit/2+1)+output['desc'][4:]
				if curopcode in opcodes:
					print("Duplicate opcode: "+curopcode)
				opcodes[curopcode]=output
		elif opcode[0]=='y':
			output=[]
			for bit in range(1, 17, 2):
				curopcode="%X%s"%(bit,opcode[1])
				output=globals()[name](name,argsplit,curopcode)
				output['opcode']=curopcode
				fleshout(output)
				output['desc']=output['desc'][:3]+str(bit/2+1)+output['desc'][4:]
				if curopcode in opcodes:
					print("Duplicate opcode: "+curopcode)
				opcodes[curopcode]=output
		else:
			output=globals()[name](name,argsplit,opcode)
			output['opcode']=opcode
			fleshout(output)
			if opcode in opcodes:
				print("Duplicate opcode: "+opcode)
			opcodes[opcode]=output
	else:
		print("// Could not find function %s"%name)
		opcodes[opcode]=None
		continue
	
temp=jsonEncode(opcodes)
print "SPC700js.opcodes="+temp
