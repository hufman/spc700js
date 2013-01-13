#!/usr/bin/python
""" Precompiler for SPC700 opcode tests
Reads in the spc700opcodes.txt table from stdin and generates Javascript code to test the spc700opcodes.js file
"""

"""
Each operation has several arguments and an opcode


"""

from sys import stdin
import traceback
import inspect
import sys


print """
function setupOpcodeTest() {
	instance = new SPC700js.instance();
}

function setupOpcode(opcodeByte, data) {
	var offset = 16;
	instance.cpu.PC = offset;

	instance.ram.set(instance, offset, opcodeByte);
	for (var i=0; i<data.length; i++) {
		instance.ram.set(instance, offset+1+i, data[i]);
	}
}

function runInstruction(cycles) {
	for (var tick=0; tick<cycles; tick++) {
		instance.cpu.tick(instance);
	}
}

"""

def arity(method):
	return len(inspect.getargspec(method)[0])

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

def module(name):
	print "module(\"%s\", {setup: setupOpcodeTest})"%name

modules={}

# operand assemblers
operands={
	'#imm': lambda v:(v,),
	'dp': lambda l:(l,),
	'dpw': lambda l:(l,),
	'dp+X': lambda l:(l,),
	'[dp+X]': lambda l:(l,),
	'dp+Y': lambda l:(l,),
	'[dp]+Y': lambda l:(l,),
	'!abs': lambda l:(l & 0xff, (l >> 8) & 0xff,),
	'!abs+X': lambda l:(l & 0xff, (l >> 8) & 0xff,),
	'!abs+Y': lambda l:(l & 0xff, (l >> 8) & 0xff,)
}
# the memory locations that each opcode refers to
addrs={
	'#imm': None,
	'A': None,
	'X': None,
	'Y': None,
	'YA': None,
	'SP': None,
	'dp': lambda cpuenv, x:'%s + %s'%(cpuenv['p']*256, x),
	'dpw': lambda cpuenv, x:'%s + %s'%(cpuenv['p']*256, x),
	'(X)': lambda cpuenv :'%s + %s'%(cpuenv['p']*256, cpuenv['X']),
	'(X)+': lambda cpuenv :'%s + %s'%(cpuenv['p']*256, cpuenv['X']),
	'(Y)': lambda cpuenv :'%s + %s'%(cpuenv['p']*256, cpuenv['Y']),
	'dp+X': lambda cpuenv, x:'%s + %s + %s'%(cpuenv['p']*256, cpuenv['X'],x),
	'[dp+X]': lambda cpuenv, x:'%s + %s + %s'%(cpuenv['p']*256, cpuenv['X'],x),
	'dp+Y': lambda cpuenv, x:'%s + %s + %s'%(cpuenv['p']*256, cpuenv['Y'],x),
	'[dp]+Y': lambda cpuenv, x:'%s + %s'%(cpuenv['p']*256, x),
	'!abs': lambda cpuenv, x:'%s'%x,
	'!abs+X': lambda cpuenv, x:'%s + %s'%(cpuenv['X'], x),
	'!abs+Y': lambda cpuenv, x:'%s + %s'%(cpuenv['Y'], x)
}
# Contains code to initialize the requested location with an initial value
setters={
	'#imm': lambda:'',	# no initialization needed here, because it's part of the assembly
	'A': lambda v:'instance.cpu.A = %s'%v,
	'X': lambda v:'instance.cpu.X = %s'%v,
	'Y': lambda v:'instance.cpu.Y = %s'%v,
	'YA': lambda v:'instance.cpu.Y = %s >> 8; instance.cpu.A = %s & 0xff'%(v,v),
	'SP': lambda v:'instance.cpu.SP = %s'%v,
	'dp': lambda l,v:'instance.ram.set(instance, %s, %s)'%(l,v),
	'dpw': lambda l,v:'instance.ram.set(instance, %s, %s & 0xff); instance.ram.set(instance, %s+1, %s >> 8)'%(l,v,l,v),
	'(X)': lambda l,v:'instance.ram.set(instance, %s, %s)'%(l,v),
	'(X)+': lambda l,v:'instance.ram.set(instance, %s, %s)'%(l,v),
	'(Y)': lambda l,v:'instance.ram.set(instance, %s, %s)'%(l,v),
	'dp+X': lambda l,v:'instance.ram.set(instance, %s, %s)'%(l,v),
	'[dp+X]': lambda p,l,v:'instance.ram.set(instance, {l}, {pl}); instance.ram.set(instance, {l}+1, {ph}); instance.ram.set(instance, {p}, {v})'.format(p=p, ph=(p&0xff00)>>8, pl=p&0xff, l=l, v=v),
	'dp+Y': lambda l,v:'instance.ram.set(instance, %s, %s)'%(l,v),
	'[dp]+Y': lambda c,p,l,v:'instance.ram.set(instance, {l}, {pl}); instance.ram.set(instance, {l}+1, {ph}); instance.ram.set(instance, {p}+{y}, {v})'.format(p=p, ph=(p&0xff00)>>8, pl=p&0xff, y=c['Y'],l=l, v=v),
	'!abs': lambda l,v:'instance.ram.set(instance, %s, %s)'%(l,v),
	'!abs+X': lambda l,v:'instance.ram.set(instance, %s, %s)'%(l,v),
	'!abs+Y': lambda l,v:'instance.ram.set(instance, %s, %s)'%(l,v)
}
# Contains code to check that the requested location has the correct value
getters={
	'#imm': None,		# should never be used
	'A': lambda:'instance.cpu.A',
	'X': lambda:'instance.cpu.X',
	'Y': lambda:'instance.cpu.Y',
	'YA': lambda:'(instance.cpu.Y << 8) + instance.cpu.A',
	'SP': lambda:'instance.cpu.SP',
	'dp': lambda l:'instance.ram.get(instance, %s)'%l,
	'dpw': lambda l:'instance.ram.get(instance, %s) + (instance.ram.get(instance, %s+1) << 8)'%(l,l),
	'(X)': lambda l:'instance.ram.get(instance, %s)'%l,
	'(X)+': lambda l:'instance.ram.get(instance, %s)'%l,
	'(Y)': lambda l:'instance.ram.get(instance, %s)'%l,
	'dp+X': lambda l:'instance.ram.get(instance, %s)'%l,
	'[dp+X]': lambda l:'instance.ram.get(instance, instance.ram.get(instance, %s) + (instance.ram.get(instance, %s+1)<<8))'%(l,l),
	'dp+Y': lambda l:'instance.ram.get(instance, %s)'%l,
	'[dp]+Y': lambda c,l:'instance.ram.get(instance, instance.ram.get(instance, {l}) + (instance.ram.get(instance, {l}+1)<<8) + {y})'.format(l=l,y=c['Y']),
	'!abs': lambda l:'instance.ram.get(instance, %s)'%l,
	'!abs+X': lambda l:'instance.ram.get(instance, %s)'%l,
	'!abs+Y': lambda l:'instance.ram.get(instance, %s)'%l
}
expects={
	'N0':'ok(instance.cpu.getPSW(instance, SPC700js.consts.PSW_N)==0, testname+": Negative flag unset")',
	'N1':'ok(instance.cpu.getPSW(instance, SPC700js.consts.PSW_N), testname+": Negative flag set")',
	'V0':'ok(instance.cpu.getPSW(instance, SPC700js.consts.PSW_V)==0, testname+": Overflow flag unset")',
	'V1':'ok(instance.cpu.getPSW(instance, SPC700js.consts.PSW_V), testname+": Overflow flag set")',
	'P0':'ok(instance.cpu.getPSW(instance, SPC700js.consts.PSW_P)==0, testname+": Page flag unset")',
	'P1':'ok(instance.cpu.getPSW(instance, SPC700js.consts.PSW_P), testname+": Page flag set")',
	'B0':'ok(instance.cpu.getPSW(instance, SPC700js.consts.PSW_B)==0, testname+": Break flag unset")',
	'B1':'ok(instance.cpu.getPSW(instance, SPC700js.consts.PSW_B), testname+": Break flag set")',
	'H0':'ok(instance.cpu.getPSW(instance, SPC700js.consts.PSW_H)==0, testname+": Halfcarry flag unset")',
	'H1':'ok(instance.cpu.getPSW(instance, SPC700js.consts.PSW_H), testname+": Halfcarry flag set")',
	'I0':'ok(instance.cpu.getPSW(instance, SPC700js.consts.PSW_I)==0, testname+": Interrupt flag unset")',
	'I1':'ok(instance.cpu.getPSW(instance, SPC700js.consts.PSW_I), testname+": Interrupt flag set")',
	'C0':'ok(instance.cpu.getPSW(instance, SPC700js.consts.PSW_C)==0, testname+": Carry flag unset")',
	'C1':'ok(instance.cpu.getPSW(instance, SPC700js.consts.PSW_C), testname+": Carry flag set")',
	'Z0':'ok(instance.cpu.getPSW(instance, SPC700js.consts.PSW_Z)==0, testname+": Zero flag unset")',
	'Z1':'ok(instance.cpu.getPSW(instance, SPC700js.consts.PSW_Z), testname+": Zero flag set")'
}

def CreateTest(setup, assembly, validation, cycles, expects):
	output = 'setupOpcodeTest();\n'

	# load up the assembly code
	output += 'setupOpcode(%s, %s);\n'%(assembly[0], jsonEncode(assembly[1:]))

	# initialize variables
	for step in setup:
		output += step + "\n"

	# run validation
	for step in validation:
		output += step + "\n"

	# run
	output += 'runInstruction(%s);\n'%cycles;

	# check expectations
	for step in expects:
		output += step + "\n"

	return output

def MemoryTransform(opname, args, opcode, bytes, cycles, opcodeflags):
	output = ''
	
	if len(args)==1:
		fromarg=args[0]
		toarg=args[0]
	if len(args)==2:
		fromarg=args[1]
		toarg=args[0]

	if len(opname)==4 and opname[-1]=='W':
		if fromarg=='dp':
			fromarg='dpw'
		if toarg=='dp':
			toarg='dpw'

	# verify that we can handle this case
	if fromarg not in setters or toarg not in getters:
		sys.stderr.write("Skipping %s %s, %s\n"%(opname, toarg, fromarg))
		return

	fromaddr = addrs[fromarg]
	fromsetter = setters[fromarg]
	fromgetter = getters[fromarg]
	toaddr = addrs[toarg]
	togetter = getters[toarg]
	if len(args)==2:
		tosetter = setters[toarg]

	testenv = {
		'source':0x50,		# source address, if we need one
		'dest': 0x60,		# dest address, if we need one
		'pointer': 0x4723,	# far pointer, if we need one
		'sample': 6,		# random number that is being moved
		'wrongsample': 9	# destination value to make sure that it is overwritten
	}
	cpuenv={
		'p':0,
		'c':0,
		'A':6,
		'X':90,
		'Y':92,
		'SP':253
	}

	if len(opname)==4 and opname[-1]=='W':
		testenv['sample'] = 1551
		testenv['wrongsample'] = 2319
	if len(args)==1 and toarg=='YA':
		testenv['sample'] = 0x670c
	if len(args)==2 and toarg=='YA':
		testenv['sample'] = 0x20		# X
		testenv['wrongsample'] = 0x170c		# YA
	def createTestWithEnv(testname, testenv, cpuenv, extrasetup, extraexpects):
		# create the setup
		setup = []
		setup.append('var testname = "%s"'%testname)
		setup.extend(extrasetup)

		if fromaddr:				# if we are setting a from address
			if arity(fromaddr)==2:		# if we need to pick an address
				thisfromaddr=fromaddr(cpuenv, testenv['source'])
			else:				# if the fromaddr doesn't need an address
				thisfromaddr=fromaddr(cpuenv)

		# set up CPU vars
		setup.append("// Setting up initial CPU flags")
		for key in cpuenv.keys():
			if key.lower()==key:
				setup.append("instance.cpu.setPSW(instance, SPC700js.consts.PSW_%s, %s)" % (key.upper(), cpuenv[key]))
			else:
				setup.append("instance.cpu.%s = %s" % (key, cpuenv[key]))
		setup.append("")

		setup.append("// Setting up source data")
		if arity(fromsetter)==4:	# we are setting up an indirect ram address which requires some late cpuenv
			setup.append(fromsetter(cpuenv, testenv['pointer'], thisfromaddr, testenv['sample']))
		elif arity(fromsetter)==3:	# we are setting up an indirect ram address
			setup.append(fromsetter(testenv['pointer'], thisfromaddr, testenv['sample']))
		elif arity(fromsetter)==2:	# we are setting a ram address
			setup.append(fromsetter(thisfromaddr, testenv['sample']))
		elif arity(fromsetter)==1:	# we are setting a register
			setup.append(fromsetter(testenv['sample']))
			cpuenv[fromarg]=testenv['sample']
		else:				# something else
			setup.append(fromsetter())

		if toaddr:				# if we are setting a to address
			if arity(toaddr)==2:		# if we need to pick an address
				thistoaddr=toaddr(cpuenv, testenv['dest'])
			else:				# if the toaddr doesn't need an address
				thistoaddr=toaddr(cpuenv)
		if len(args)==1 and fromaddr:	# destination will be the same
			thistoaddr=thisfromaddr

		if len(args)==2:	# the destination is different, populate it
			if arity(tosetter)==4:		# we are setting a ram address and a pointer and a late cpu env
				setup.append(tosetter(cpuenv, testenv['pointer'], thistoaddr, testenv['wrongsample']))
			elif arity(tosetter)==3:		# we are setting a ram address and a pointer
				setup.append(tosetter(testenv['pointer'], thistoaddr, testenv['wrongsample']))
			elif arity(tosetter)==2:		# we are setting a ram address
				setup.append(tosetter(thistoaddr, testenv['wrongsample']))
			elif arity(tosetter)==1:	# we are setting a register
				setup.append(tosetter(testenv['wrongsample']))
				cpuenv[toarg]=testenv['wrongsample']
			else:				# something else
				setup.append(tosetter())
		setup.append("")


		# generate assembly
		assembly=[int(opcode, 16)]
		if fromarg in operands:			# we have to encode part of this in the assembly
			if fromaddr:		# we have to encode an address
				assembly[1:1]=(operands[fromarg](testenv['source']))
			else:						# we have to encode a data
				assembly[1:1]=(operands[fromarg](testenv['sample']))

		if len(args)==2 and toarg in operands:			# we have to encode part of this in the assembly
			if toaddr:		# we have to encode an address
				assembly[1:1]=(operands[toarg](testenv['dest']))
			else:						# we have to encode a data   like #imm
				assembly[1:1]=(operands[toarg](testenv['sample']))

		# validate that the system is setup right
		offset = 16
		validation=[]
		validation.append("var opcode = instance.disassembled.get(instance, %s)"%offset)
		validation.append("equal(opcode.nextLocation(instance, %s), %s, 'Correct step to next instruction')" % (offset, offset + len(assembly)))
		if fromaddr:
			validation.append("equal(opcode.readAddress(instance, %s), %s, 'Correct read address')" % (offset, thisfromaddr))
		if toaddr:
			validation.append("equal(opcode.writeAddress(instance, %s), %s, 'Correct write address')" % (offset, thistoaddr))
		validation.append("equal(opcode.readValue(instance, %s), %s, 'Correct source value')" % (offset, testenv['sample']))
		if len(args)==2:
			validation.append("equal(opcode.readOrigWriteValue(instance, %s), %s, 'Correct destination value')" % (offset, testenv['wrongsample']))


		# check source value to be unchanged
		expects = []
		if len(args)==2:
			if fromgetter and arity(fromgetter)==2:					# if the code was reading from ram and using a register offset
				expects.append('equal(%s, %s, testname+": Source unchanged");\n' % (fromgetter(cpuenv, thisfromaddr), testenv['sample']))
			if fromgetter and arity(fromgetter)==1:					# if the code was reading from ram
				expects.append('equal(%s, %s, testname+": Source unchanged");\n' % (fromgetter(thisfromaddr), testenv['sample']))
			elif fromgetter and arity(fromgetter)==0:					# if the code was reading from a register
				expects.append('equal(%s, %s, testname+": Source unchanged");\n'%(fromgetter(), testenv['sample']))
			else:										# something else
				pass

		# check destination value
		if opname=='MOV':
			transform = lambda x:x
		if opname=='ADC':
			if args[0]=='A':
				transform = lambda x: x + cpuenv['A'] + cpuenv['c']
			if args[0]=='(X)':
				transform = lambda x: x + testenv['wrongsample'] + cpuenv['c']
			if args[0]=='dp':
				transform = lambda x: x + testenv['wrongsample'] + cpuenv['c']
		if opname=='SBC':
			if args[0]=='A':
				transform = lambda x: cpuenv['A'] - (x + 1-cpuenv['c'])
			if args[0]=='(X)':
				transform = lambda x: testenv['wrongsample'] - (x + 1-cpuenv['c'])
			if args[0]=='dp':
				transform = lambda x: testenv['wrongsample'] - (x + 1-cpuenv['c'])
		if opname=='CMP':
			transform = lambda x: testenv['wrongsample']
		if opname=='AND':
			transform = lambda x: testenv['wrongsample'] & testenv['sample']
		if opname=='OR':
			transform = lambda x: testenv['wrongsample'] | testenv['sample']
		if opname=='EOR':
			transform = lambda x: testenv['wrongsample'] ^ testenv['sample']
		if opname=='INC':
			transform = lambda x: testenv['sample'] + 1
		if opname=='DEC':
			transform = lambda x: testenv['sample'] - 1
		if opname=='ASL':
			transform = lambda x: testenv['sample'] << 1
		if opname=='LSR':
			transform = lambda x: testenv['sample'] >> 1
		if opname=='ROL':
			transform = lambda x: (testenv['sample'] << 1) + cpuenv['c']
		if opname=='ROR':
			transform = lambda x: (testenv['sample'] >> 1) + (cpuenv['c'] * 128)
		if opname=='XCN':
			transform = lambda x: (testenv['sample'] >> 4) + (testenv['sample'] << 4) & 0xf0
		if opname=='MOVW':
			transform = lambda x:x
		if opname=='INCW':
			transform = lambda x: testenv['sample'] + 1
		if opname=='DECW':
			transform = lambda x: testenv['sample'] - 1
		if opname=='ADDW':
			transform = lambda x: testenv['wrongsample'] + testenv['sample']
		if opname=='SUBW':
			transform = lambda x: testenv['wrongsample'] - testenv['sample']
		if opname=='CMPW':
			transform = lambda x: testenv['wrongsample']
		if opname=='MUL':
			transform = lambda x: (testenv['sample'] >> 8) * (testenv['sample'] & 0xff)
		if opname=='DIV':
			transform = lambda x: (testenv['wrongsample'] / testenv['sample'])

		if len(opname)==4 and opname[-1]=='W' or toarg=='YA':
			newsample = (transform(testenv['sample']) + 65536) % 65536
		else:
			newsample = (transform(testenv['sample']) + 256) % 256
		
		# check the destination value
		if opname=='DIV':
			expects.append('equal(%s, %s, testname+": Correct A (result)");\n'%(getters['A'](), newsample))
			expects.append('equal(%s, %s, testname+": Correct Y (modulus)");\n'%(getters['Y'](), (testenv['wrongsample'] % testenv['sample']) % 256))
		elif togetter and arity(togetter)==2:					# if we are setting a ram address that needs a register offset
			expects.append('equal(%s, %s, testname+": Correct destination");\n'%(togetter(cpuenv,thistoaddr), newsample))
		elif togetter and arity(togetter)==1:					# if we are setting a ram address
			expects.append('equal(%s, %s, testname+": Correct destination");\n'%(togetter(thistoaddr), newsample))
		elif togetter and arity(togetter)==0:				# set a register
			expects.append('equal(%s, %s, testname+": Correct destination");\n'%(togetter(), newsample))
		else:									# something else
			pass

		# load up any others
		expects.extend(extraexpects)

		return CreateTest(setup, assembly, validation, cycles, expects)

	# load up the dependent flags
	totalflags = ['N', 'V', 'P', 'B', 'H', 'I', 'Z', 'C']
	dependentflags=[]
	dpargs = ['dp', '(X)', '(Y)']
	if fromarg in dpargs or toarg in dpargs:
		dependentflags.append('P')
	if opname in ['ADC', 'SBC', 'ROL', 'ROR']:
		dependentflags.append('C')
	for test in range(0, 2**len(dependentflags)):
		extrasetup = []
		extraexpect = []
		thiscpuenv = dict(cpuenv)
		name = opname
		for index in range(0, len(dependentflags)):
			flag=dependentflags[index]
			thiscpuenv[flag.lower()] = min(1, (test % (2**(index+1))))
			if thiscpuenv[flag.lower()] == 1:
				name+=" "+flag

		# do two tests to verify non-setting flags
		untouchedflags = set(totalflags) - set(dependentflags) - set(opcodeflags)
		for value in [0, 1]:
			anothername = name + " doesn't touch %s"%('set' if value else 'unset')
			anothercpuenv = dict(thiscpuenv)
			anotherexpect = list(extraexpect)
			for flag in untouchedflags:
				anothercpuenv[flag.lower()] = value
				anotherexpect.append(expects[flag + str(value)])
			output += createTestWithEnv(anothername, testenv, anothercpuenv, extrasetup, anotherexpect)
		
	# try out some cpu flags
	extrasetup = []
	extraexpect = []
	if opname == 'MOV':
		if toarg in ['A', 'X', 'Y']:
			testenv['sample']=160
			extraexpect.append(expects['N1'])
			extraexpect.append(expects['Z0'])
			output += createTestWithEnv('MOV for Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

			extrasetup=[]
			extraexpect=[]
			testenv['sample']=0
			extraexpect.append(expects['N0'])
			extraexpect.append(expects['Z1'])
			output += createTestWithEnv('MOV for Zero Flag', testenv, cpuenv, extrasetup, extraexpect)
	elif opname == 'ADC':
		testenv['sample']=125
		testenv['wrongsample']=20
		extraexpect.append(expects['N1'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv('ADC for Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect=[]
		testenv['sample']=254
		testenv['wrongsample']=2
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z1'])
		extraexpect.append(expects['V1'])
		extraexpect.append(expects['C1'])
		output += createTestWithEnv('ADC for Zero Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect=[]
		testenv['sample']=254
		testenv['wrongsample']=4
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z0'])
		extraexpect.append(expects['V1'])
		extraexpect.append(expects['C1'])
		output += createTestWithEnv('ADC for Carry Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect=[]
		testenv['sample']=8
		testenv['wrongsample']=4
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z0'])
		extraexpect.append(expects['V0'])
		extraexpect.append(expects['C0'])
		extraexpect.append(expects['H1'])
		output += createTestWithEnv('ADC for Halfcarry Flag', testenv, cpuenv, extrasetup, extraexpect)
	elif opname == 'SBC':
		testenv['sample']=100
		testenv['wrongsample']=20
		extraexpect.append(expects['N1'])
		extraexpect.append(expects['C0'])
		extraexpect.append(expects['V1'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv('SBC for Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

		testenv['sample']=2
		testenv['wrongsample']=0x80
		extraexpect = []
		extraexpect.append(expects['V1'])
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['C1'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv('SBC for Overflow+Carry Flag', testenv, cpuenv, extrasetup, extraexpect)

		testenv['sample']=0x80
		testenv['wrongsample']=0x20
		extraexpect = []
		extraexpect.append(expects['V1'])
		extraexpect.append(expects['N1'])
		extraexpect.append(expects['C0'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv('SBC for Overflow+Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

		testenv['sample']=4
		testenv['wrongsample']=6
		extraexpect = []
		extraexpect.append(expects['C1'])
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['V0'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv('SBC for Carry Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect=[]
		testenv['sample']=120
		testenv['wrongsample']=121
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['C1'])
		extraexpect.append(expects['V0'])
		extraexpect.append(expects['Z1'])
		output += createTestWithEnv('SBC for Zero Flag', testenv, cpuenv, extrasetup, extraexpect)

		thiscpuenv=dict(cpuenv)
		thiscpuenv['c']=1
		extraexpect=[]
		testenv['sample']=121
		testenv['wrongsample']=121
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z1'])
		output += createTestWithEnv('SBC C for Zero Flag', testenv, thiscpuenv, extrasetup, extraexpect)
	elif opname == 'CMP':
		testenv['sample']=100
		testenv['wrongsample']=20
		extraexpect = []
		extraexpect.append(expects['N1'])
		extraexpect.append(expects['C0'])
		extraexpect.append(expects['V0'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv('CMP for Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

		testenv['sample']=1
		testenv['wrongsample']=0x80
		extraexpect = []
		extraexpect.append(expects['V1'])
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['C1'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv('CMP for Overflow+Carry Flag', testenv, cpuenv, extrasetup, extraexpect)

		testenv['sample']=0x80
		testenv['wrongsample']=0x20
		extraexpect = []
		extraexpect.append(expects['V1'])
		extraexpect.append(expects['N1'])
		extraexpect.append(expects['C0'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv('CMP for Overflow+Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

		testenv['sample']=4
		testenv['wrongsample']=5
		extraexpect = []
		extraexpect.append(expects['C1'])
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['V0'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv('CMP for Carry Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect=[]
		testenv['sample']=120
		testenv['wrongsample']=120
		extraexpect = []
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['V0'])
		extraexpect.append(expects['Z1'])
		extraexpect.append(expects['C1'])
		output += createTestWithEnv('CMP for Zero Flag', testenv, cpuenv, extrasetup, extraexpect)
	elif opname in ['AND']:
		testenv['sample'] = 85
		testenv['wrongsample'] = 170
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z1'])
		output += createTestWithEnv(opname+' for Zero Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect = []
		testenv['sample'] = 240
		testenv['wrongsample'] = 143
		extraexpect.append(expects['N1'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv(opname+' for Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

	elif opname in ['OR']:
		testenv['sample'] = 0
		testenv['wrongsample'] = 0
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z1'])
		output += createTestWithEnv(opname+' for Zero Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect = []
		testenv['sample'] = 240
		testenv['wrongsample'] = 143
		extraexpect.append(expects['N1'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv(opname+' for Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

	elif opname in ['EOR']:
		testenv['sample'] = 250
		testenv['wrongsample'] = 250
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z1'])
		output += createTestWithEnv(opname+' for Zero Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect = []
		testenv['sample'] = 113
		testenv['wrongsample'] = 143
		extraexpect.append(expects['N1'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv(opname+' for Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

	elif opname in ['INC']:
		testenv['sample'] = 255
		testenv['wrongsample'] = 255
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z1'])
		output += createTestWithEnv(opname+' for Zero Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect = []
		testenv['sample'] = 127
		testenv['wrongsample'] = 127
		extraexpect.append(expects['N1'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv(opname+' for Negative Flag', testenv, cpuenv, extrasetup, extraexpect)
	elif opname in ['DEC']:
		testenv['sample'] = 1
		testenv['wrongsample'] = 1
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z1'])
		output += createTestWithEnv(opname+' for Zero Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect = []
		testenv['sample'] = 0
		testenv['wrongsample'] = 0
		extraexpect.append(expects['N1'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv(opname+' for Negative Flag', testenv, cpuenv, extrasetup, extraexpect)
	elif opname in ['ASL', 'ROL']:
		testenv['sample'] = 128
		extraexpect.append(expects['C1'])
		output += createTestWithEnv(opname+' for Carry Flag', testenv, cpuenv, extrasetup, extraexpect)
	elif opname in ['LSR', 'ROR']:
		testenv['sample'] = 129
		extraexpect.append(expects['C1'])
		output += createTestWithEnv(opname+' for Carry Flag', testenv, cpuenv, extrasetup, extraexpect)

	if opname == 'MOVW':
		if toarg in ['YA']:
			testenv['sample']=160
			extraexpect.append(expects['N0'])
			extraexpect.append(expects['Z0'])
			output += createTestWithEnv('MOVW for unset Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

			extrasetup=[]
			extraexpect=[]
			testenv['sample']=32640		# 0xff00 >> 1
			extraexpect.append(expects['N0'])
			extraexpect.append(expects['Z0'])
			output += createTestWithEnv('MOVW for unset Zero Flag', testenv, cpuenv, extrasetup, extraexpect)
			extrasetup=[]
			extraexpect=[]
			testenv['sample']=65280		# 0xff00
			extraexpect.append(expects['N1'])
			extraexpect.append(expects['Z0'])
			output += createTestWithEnv('MOVW for Negative Flag', testenv, cpuenv, extrasetup, extraexpect)
	if opname == 'INCW':
		testenv['sample']=127
		testenv['wrongsample']=127
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv('INCW for unset Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

		extrasetup=[]
		extraexpect=[]
		testenv['sample']=255
		testenv['wrongsample']=255
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv('INCW for unset Zero Flag', testenv, cpuenv, extrasetup, extraexpect)
		extrasetup=[]
		extraexpect=[]
		testenv['sample']=32767		# 0x7fff
		extraexpect.append(expects['N1'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv('INCW for Negative Flag', testenv, cpuenv, extrasetup, extraexpect)
		extrasetup=[]
		extraexpect=[]
		testenv['sample']=65535		# 0xfff
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z1'])
		output += createTestWithEnv('INCW for Zero Flag', testenv, cpuenv, extrasetup, extraexpect)
	if opname == 'DECW':
		testenv['sample']=4096
		testenv['wrongsample']=4096
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv('DECW for unset Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

		extrasetup=[]
		extraexpect=[]
		testenv['sample']=4097
		testenv['wrongsample']=4097
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv('DECW for unset Zero Flag', testenv, cpuenv, extrasetup, extraexpect)
		extrasetup=[]
		extraexpect=[]
		testenv['sample']=0
		extraexpect.append(expects['N1'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv('DECW for Negative Flag', testenv, cpuenv, extrasetup, extraexpect)
		extrasetup=[]
		extraexpect=[]
		testenv['sample']=1
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z1'])
		output += createTestWithEnv('DECW for Zero Flag', testenv, cpuenv, extrasetup, extraexpect)

	elif opname == 'ADDW':
		testenv['sample']=0x7ffe
		testenv['wrongsample']=20
		extraexpect.append(expects['N1'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv('ADDW for Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect=[]
		testenv['sample']=0xfffe
		testenv['wrongsample']=2
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z1'])
		extraexpect.append(expects['V1'])
		extraexpect.append(expects['C1'])
		output += createTestWithEnv('ADDW for Zero Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect=[]
		testenv['sample']=0xfffe
		testenv['wrongsample']=4
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z0'])
		extraexpect.append(expects['V1'])
		extraexpect.append(expects['C1'])
		output += createTestWithEnv('ADDW for Carry Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect=[]
		testenv['sample']=8
		testenv['wrongsample']=4
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z0'])
		extraexpect.append(expects['V0'])
		extraexpect.append(expects['C0'])
		extraexpect.append(expects['H1'])
		output += createTestWithEnv('ADDW for Halfcarry Flag', testenv, cpuenv, extrasetup, extraexpect)
	elif opname in ['SUBW', 'CMPW']:
		testenv['sample']=5
		testenv['wrongsample']=0x0300
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv(opname + ' for unset Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect=[]
		testenv['sample']=0x4500
		testenv['wrongsample']=0x100
		extraexpect.append(expects['N1'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv(opname + ' for Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect=[]
		testenv['sample']=0x4500
		testenv['wrongsample']=0x4500
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z1'])
		output += createTestWithEnv(opname + ' for Zero Flag', testenv, cpuenv, extrasetup, extraexpect)
	elif opname in ['MUL']:
		extraexpect=[]
		testenv['sample']=0xffc0
		extraexpect.append(expects['N1'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv(opname + ' for Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect=[]
		testenv['sample']=0xfc00
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z1'])
		output += createTestWithEnv(opname + ' for Zero Flag', testenv, cpuenv, extrasetup, extraexpect)

	elif opname in ['DIV']:
		extraexpect=[]
		testenv['sample']=2
		testenv['wrongsample']=400
		extraexpect.append(expects['N1'])
		extraexpect.append(expects['Z0'])
		output += createTestWithEnv(opname + ' for Negative Flag', testenv, cpuenv, extrasetup, extraexpect)

		extraexpect=[]
		testenv['sample']=2
		testenv['wrongsample']=0
		extraexpect.append(expects['N0'])
		extraexpect.append(expects['Z1'])
		output += createTestWithEnv(opname + ' for Zero Flag', testenv, cpuenv, extrasetup, extraexpect)

	if opname not in modules:
		modules[opname]={}
	modules[opname][','.join(args)]=output

def MOV(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def ADC(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def SBC(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def CMP(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def AND(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def OR(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def EOR(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def INC(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def DEC(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def ASL(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def LSR(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def ROL(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def ROR(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def XCN(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def MOVW(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def INCW(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def DECW(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def ADDW(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def SUBW(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def CMPW(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def MUL(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)
def DIV(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	MemoryTransform(opname, args, opcode, bytes, morecycles, flags)

def SCENARIOS(opname, opcode, name, scenarios):
	if opname not in modules:
		modules[opname] = {}
	output = ''
	for scenario in scenarios:
		assembly = [int(opcode, 16)]
		assembly.extend(scenario['data'])
		checksPC = reduce(lambda x,y:x or y, map(lambda x: 'PC' in x, scenario['expects']), False)
		if not checksPC:
			scenario['expects'].insert(0, "equal(instance.cpu.PC, 16 + %s, 'Correct step to next instruction')"%(len(scenario['data'])+1))
		validation = ["var opcode = instance.disassembled.get(instance, 16)"]
		validation.extend(scenario['validation'] if 'validation' in scenario.keys() else [])
		output += CreateTest(scenario['setup'], assembly, validation, scenario['cycles'], scenario['expects'])
	modules[opname][name] = output
def BRANCH(opname, opcode, name, scenarios):
	SCENARIOS(opname, opcode, name, scenarios)

def BRA(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	scenario = {"name":"", "setup":[], "data":[4], "cycles":morecycles, "expects":["equal(instance.cpu.PC, 16+2+4, 'Branched')"]}
	BRANCH(opname, opcode, 'Branch Always', [scenario])

def BRANCHFLAG(opname, args, opcode, name, bytes, lesscycles, morecycles, flag, shouldbe):
	validation = ["equal(opcode.branchTrueDest(instance,16), 16+2+4, 'Correct branch destination')", "equal(opcode.nextLocation(instance,16), 16+2, 'Correct next opcode')", "equal(opcode.readAddress(instance,16), '%s', 'Correct flag')"%flag, "equal(opcode.testResult(instance,16), true, 'Correct branch outcome')"]
	goodscenario1 = {"name":"Branch", "data":[4], "setup":['instance.cpu.setPSW(instance,SPC700js.consts.PSW_%s, %i)'%(flag,shouldbe)], "validation":validation, "cycles":morecycles, "expects":["equal(instance.cpu.PC, 16+2+4, 'Branched')"]}
	validation = ["equal(opcode.branchTrueDest(instance,16), 16+2-4, 'Correct branch destination')", "equal(opcode.nextLocation(instance,16), 16+2, 'Correct next opcode')", "equal(opcode.readAddress(instance,16), '%s', 'Correct flag')"%flag, "equal(opcode.testResult(instance,16), true, 'Correct branch outcome')"]
	goodscenario2 = {"name":"Back Branch", "data":[252], "setup":['instance.cpu.setPSW(instance,SPC700js.consts.PSW_%s, %i)'%(flag,shouldbe)], "validation":validation, "cycles":morecycles, "expects":["equal(instance.cpu.PC, 16+2-4, 'Branched')"]}
	validation = ["equal(opcode.branchTrueDest(instance,16), 16+2+4, 'Correct branch destination')", "equal(opcode.nextLocation(instance,16), 16+2, 'Correct next opcode')", "equal(opcode.readAddress(instance,16), '%s', 'Correct flag')"%flag, "equal(opcode.testResult(instance,16), false, 'Correct branch outcome')"]
	badscenario = {"name":"Not Branch", "data":[4], "setup":['instance.cpu.setPSW(instance,SPC700js.consts.PSW_%s, %i)'%(flag,1-shouldbe)], "validation":validation, "cycles":lesscycles, "expects":["equal(instance.cpu.PC, 16+2+0, 'Not Branched')"]}
	BRANCH(opname, opcode, name, [goodscenario1, goodscenario2, badscenario])
def BEQ(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	BRANCHFLAG(opname, args, opcode, 'Branch Equal', bytes, lesscycles, morecycles, 'Z', 1)
def BNE(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	BRANCHFLAG(opname, args, opcode, 'Branch Not Equal', bytes, lesscycles, morecycles, 'Z', 0)
def BCS(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	BRANCHFLAG(opname, args, opcode, 'Branch Carry Set', bytes, lesscycles, morecycles, 'C', 1)
def BCC(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	BRANCHFLAG(opname, args, opcode, 'Branch Carry Clear', bytes, lesscycles, morecycles, 'C', 0)
def BVS(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	BRANCHFLAG(opname, args, opcode, 'Branch Overflow Set', bytes, lesscycles, morecycles, 'V', 1)
def BVC(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	BRANCHFLAG(opname, args, opcode, 'Branch Overflow Clear', bytes, lesscycles, morecycles, 'V', 0)
def BMI(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	BRANCHFLAG(opname, args, opcode, 'Branch Negative', bytes, lesscycles, morecycles, 'N', 1)
def BPL(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	BRANCHFLAG(opname, args, opcode, 'Branch Positive', bytes, lesscycles, morecycles, 'N', 0)

def BRANCHBIT(opname, args, opcode, bytes, lesscycles, morecycles, shouldbe):
	for bit in range(0,8):
		scenarios=[]
		bitmask = 2**bit
		if shouldbe == 0:
			bitmask = 255 - bitmask
		opcode = ("%x"%(bit*2 + (1-shouldbe))) + opcode[1]
		for dp in [0, 1]:
			ram = 8 if dp==0 else 8+256
			name = "Branch "+str(bit+1)+" P"+str(dp)
			setup = ['instance.ram.set(instance, %i, %i)'%(ram,bitmask),'instance.cpu.setPSW(instance,SPC700js.consts.PSW_P, %s)'%dp]
			validation = ["equal(opcode.branchTrueDest(instance,16), 16+3+4, 'Correct branch destination')", "equal(opcode.nextLocation(instance,16), 16+3, 'Correct next opcode')", "equal(opcode.readAddress(instance,16), '%s', 'Correct read address')"%ram, "equal(opcode.testResult(instance,16), true, 'Correct branch outcome')"]
			goodscenario1 = {"name":"Branch "+str(bit+1)+" P"+str(dp), "data":[8,4], "setup":setup, "validation":validation, "cycles":morecycles, "expects":["equal(instance.cpu.PC, 16+3+4, '%s - Branched')" % name]}
			validation = ["equal(opcode.branchTrueDest(instance,16), 16+3-4, 'Correct branch destination')", "equal(opcode.nextLocation(instance,16), 16+3, 'Correct next opcode')", "equal(opcode.readAddress(instance,16), '%s', 'Correct read address')"%ram, "equal(opcode.testResult(instance,16), true, 'Correct branch outcome')"]
			goodscenario2 = {"name":"Back Branch "+str(bit+1)+" P"+str(dp), "data":[8,252], "setup":setup, "validation":validation, "cycles":morecycles, "expects":["equal(instance.cpu.PC, 16+3-4, '%s - Back Branched')" % name]}
			validation = ["equal(opcode.branchTrueDest(instance,16), 16+3+4, 'Correct branch destination')", "equal(opcode.nextLocation(instance,16), 16+3, 'Correct next opcode')", "equal(opcode.readAddress(instance,16), '%s', 'Correct read address')"%ram, "equal(opcode.testResult(instance,16), false, 'Correct branch outcome')"]
			badscenario = {"name":"Not Branch "+str(bit+1)+" P"+str(dp), "data":[8,4], "setup":['instance.ram.set(instance, %i, %i)'%(ram,255-bitmask),'instance.cpu.setPSW(instance,SPC700js.consts.PSW_P, %s)'%dp], "validation":validation, "cycles":lesscycles, "expects":["equal(instance.cpu.PC, 16+3+0, '%s - Not Branched')" % name]}
			scenarios.append(goodscenario1)
			scenarios.append(goodscenario2)
			scenarios.append(badscenario)
		BRANCH(opname, opcode, opname + str(bit+1), scenarios)
def BBS(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	BRANCHBIT(opname, args, opcode, bytes, lesscycles, morecycles, 1)
def BBC(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	BRANCHBIT(opname, args, opcode, bytes, lesscycles, morecycles, 0)

def CBNE(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	if opcode=='2E':	# (dp)
		testname = "Branch if A != (dp)"
		X = 0
	if opcode=='DE':	# (dp+X)
		testname = "Branch if A != (dp+X)"
		X = 50
	scenarios = []
	for dp in [0, 1]:
		name = "P %s"%dp
		ram = 8 if dp==0 else 8+256
		otherram = 8+256 if dp==0 else 8
		ram += X
		otherram += X
		validations = [
			["equal(opcode.branchTrueDest(instance,16), 16+3+4, 'Correct branch destination')", "equal(opcode.nextLocation(instance,16), 16+3, 'Correct next opcode')", "equal(opcode.readAddress(instance,16), '%s', 'Correct read address')"%ram, "equal(opcode.testResult(instance,16), true, 'Correct branch outcome')"],
			["equal(opcode.branchTrueDest(instance,16), 16+3-4, 'Correct branch destination')", "equal(opcode.nextLocation(instance,16), 16+3, 'Correct next opcode')", "equal(opcode.readAddress(instance,16), '%s', 'Correct read address')"%ram, "equal(opcode.testResult(instance,16), true, 'Correct branch outcome')"],
			["equal(opcode.branchTrueDest(instance,16), 16+3+4, 'Correct branch destination')", "equal(opcode.nextLocation(instance,16), 16+3, 'Correct next opcode')", "equal(opcode.readAddress(instance,16), '%s', 'Correct read address')"%ram, "equal(opcode.testResult(instance,16), false, 'Correct branch outcome')"]
		]
		scenarios += [
			{"data":[8,4], "setup":['instance.ram.set(instance, %s, 13)'%ram, 'instance.ram.set(instance, %s, 12)'%otherram, 'instance.cpu.A = 12', 'instance.cpu.X = %s'%X, 'instance.cpu.setPSW(instance, SPC700js.consts.PSW_P, %s)'%dp], "validation":validations[0], "cycles":morecycles, "expects":["equal(instance.cpu.PC, 16+3+4, '%s - Branched')" % name]},
			{"data":[8,252], "setup":['instance.ram.set(instance, %s, 13)'%ram, 'instance.ram.set(instance, %s, 12)'%otherram, 'instance.cpu.A = 12', 'instance.cpu.X = %s'%X, 'instance.cpu.setPSW(instance, SPC700js.consts.PSW_P, %s)'%dp], "validation":validations[1], "cycles":morecycles, "expects":["equal(instance.cpu.PC, 16+3-4, '%s - Back Branched')" % name]},
			{"data":[8,4], "setup":['instance.ram.set(instance, %s, 13)'%ram, 'instance.ram.set(instance, %s, 12)'%otherram, 'instance.cpu.A = 13', 'instance.cpu.X = %s'%X, 'instance.cpu.setPSW(instance, SPC700js.consts.PSW_P, %s)'%dp], "validation":validations[2], "cycles":lesscycles, "expects":["equal(instance.cpu.PC, 16+3, '%s - Not Branched')" % name]}
		]
	BRANCH(opname, opcode, testname, scenarios)

def DBNZ(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	scenarios = []
	if opcode == '6E':
		testname = "--(dp) and branch != 0"
		for dp in [0, 1]:
			name = "P %s"%dp
			ram = 8 if dp==0 else 8+256
			otherram = 8+256 if dp==0 else 8

			validations = [
				["equal(opcode.branchTrueDest(instance,16), 16+3+4, 'Correct branch destination')", "equal(opcode.nextLocation(instance,16), 16+3, 'Correct next opcode')", "equal(opcode.readAddress(instance,16), '%s', 'Correct read address')"%ram, "equal(opcode.testResult(instance,16), true, 'Correct branch outcome')"],
				["equal(opcode.branchTrueDest(instance,16), 16+3-4, 'Correct branch destination')", "equal(opcode.nextLocation(instance,16), 16+3, 'Correct next opcode')", "equal(opcode.readAddress(instance,16), '%s', 'Correct read address')"%ram, "equal(opcode.testResult(instance,16), true, 'Correct branch outcome')"],
				["equal(opcode.branchTrueDest(instance,16), 16+3+4, 'Correct branch destination')", "equal(opcode.nextLocation(instance,16), 16+3, 'Correct next opcode')", "equal(opcode.readAddress(instance,16), '%s', 'Correct read address')"%ram, "equal(opcode.testResult(instance,16), false, 'Correct branch outcome')"]
			]
			scenarios += [
				{"data":[8,4], "setup":['instance.ram.set(instance, %s, 2)'%ram, 'instance.ram.set(instance, %s, 1)'%otherram, 'instance.cpu.setPSW(instance, SPC700js.consts.PSW_P, %s)'%dp], "validation":validations[0], "cycles":morecycles, "expects":["equal(instance.cpu.PC, 16+3+4, '%s - Branched')" % name, "equal(instance.ram.get(instance, %s),1,'%s - Decremented properly')"%(ram,name), "equal(instance.ram.get(instance, %s),1,'%s - Didn\\'t decrement improperly')"%(otherram,name)]},
				{"data":[8,252], "setup":['instance.ram.set(instance, %s, 2)'%ram, 'instance.ram.set(instance, %s, 2)'%otherram, 'instance.cpu.setPSW(instance, SPC700js.consts.PSW_P, %s)'%dp], "validation":validations[1], "cycles":morecycles, "expects":["equal(instance.cpu.PC, 16+3-4, '%s - Negative Branch')" % name, "equal(instance.ram.get(instance, %s),1,'%s - Decremented properly')"%(ram,name), "equal(instance.ram.get(instance, %s),2,'%s - Didn\\'t decrement improperly')"%(otherram,name)]},
				{"data":[8,4], "setup":['instance.ram.set(instance, %s, 1)'%ram, 'instance.ram.set(instance, %s, 2)'%otherram, 'instance.cpu.setPSW(instance, SPC700js.consts.PSW_P, %s)'%dp], "validation":validations[2], "cycles":lesscycles, "expects":["equal(instance.cpu.PC, 16+3+0, '%s - Didn\\'t Branch')" % name, "equal(instance.ram.get(instance, %s),0,'%s - Decremented properly')"%(ram,name), "equal(instance.ram.get(instance, %s),2,'%s - Didn\\'t decrement improperly')"%(otherram,name)]},
				{"data":[8,4], "setup":['instance.ram.set(instance, %s, 0)'%ram, 'instance.ram.set(instance, %s, 2)'%otherram, 'instance.cpu.setPSW(instance, SPC700js.consts.PSW_P, %s)'%dp], "validation":validations[0], "cycles":morecycles, "expects":["equal(instance.cpu.PC, 16+3+4, '%s - Negative Branch')" % name, "equal(instance.ram.get(instance, %s),255,'%s - Decremented properly')"%(ram,name), "equal(instance.ram.get(instance, %s),2,'%s - Didn\\'t decrement improperly')"%(otherram,name)]}
			]
	if opcode == 'FE':
		testname = "--Y and branch != 0"
		validations = [
			["equal(opcode.branchTrueDest(instance,16), 16+2+4, 'Correct branch destination')", "equal(opcode.nextLocation(instance,16), 16+2, 'Correct next opcode')", "equal(opcode.readAddress(instance,16), 'Y', 'Correct read address')", "equal(opcode.testResult(instance,16), true, 'Correct branch outcome')"],
			["equal(opcode.branchTrueDest(instance,16), 16+2-4, 'Correct branch destination')", "equal(opcode.nextLocation(instance,16), 16+2, 'Correct next opcode')", "equal(opcode.readAddress(instance,16), 'Y', 'Correct read address')", "equal(opcode.testResult(instance,16), true, 'Correct branch outcome')"],
			["equal(opcode.branchTrueDest(instance,16), 16+2+4, 'Correct branch destination')", "equal(opcode.nextLocation(instance,16), 16+2, 'Correct next opcode')", "equal(opcode.readAddress(instance,16), 'Y', 'Correct read address')", "equal(opcode.testResult(instance,16), false, 'Correct branch outcome')"]
		]
		scenarios += [
			{"data":[4], "setup":['instance.cpu.Y=2'], "validation":validations[0], "cycles":morecycles, "expects":["equal(instance.cpu.PC, 16+2+4, 'Branched')", "equal(instance.cpu.Y, 1, 'Decremented properly')"]},
			{"data":[252], "setup":['instance.cpu.Y=2'], "validation":validations[1], "cycles":morecycles, "expects":["equal(instance.cpu.PC, 16+2-4, 'Branched')", "equal(instance.cpu.Y, 1, 'Decremented properly')"]},
			{"data":[4], "setup":['instance.cpu.Y=1'], "validation":validations[2], "cycles":lesscycles, "expects":["equal(instance.cpu.PC, 16+2+0, 'Not branched')", "equal(instance.cpu.Y, 0, 'Decremented properly')"]},
			{"data":[4], "setup":['instance.cpu.Y=0'], "validation":validations[0], "cycles":morecycles, "expects":["equal(instance.cpu.PC, 16+2+4, 'Negative branch')", "equal(instance.cpu.Y, 255, 'Decremented properly')"]}
		]
	BRANCH(opname, opcode, testname, scenarios)

def JMP(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	if opcode == '5F':	# !abs
		testname = "Jump to abs"
		validation=["equal(opcode.jumpDest(instance, 16), 0xcdef, 'Correct jump destination')"]
		scenarios = [
			{"data":[0xef,0xcd], "setup":[], "validation":validation, "cycles":morecycles, "expects":["equal(instance.cpu.PC, 0xcdef, 'Jumped')"]}
		]
	if opcode == '1F':	# !abs+X
		testname = "Jump to abs:(abs+X)"
		validation=["equal(opcode.jumpDest(instance, 16), 0x5678, 'Correct jump destination')"]
		scenarios = [
			{"data":[0xef,0xcd], "setup":["instance.ram.set(instance, 0xcdef, 0x78)","instance.ram.set(instance, 0xcdf0, 0x56)"], "validation":validation, "cycles":morecycles, "expects":["equal(instance.cpu.PC, 0x5678, 'Jumped')"]},
			{"data":[0xef-100,0xcd], "setup":["instance.ram.set(instance, 0xcdef, 0x78)","instance.ram.set(instance, 0xcdf0, 0x56)","instance.cpu.X=100"], "validation":validation, "cycles":morecycles, "expects":["equal(instance.cpu.PC, 0x5678, 'Jumped')"]}
		]
	BRANCH(opname, opcode, testname, scenarios)

def CALL(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	validation = ["equal(opcode.callDest(instance, 16), 0xcdef, 'Correct call address')"]
	scenarios = [
		{"data":[0xef,0xcd], "setup":['instance.cpu.SP = 50'], "validation":validation, "cycles":morecycles, "expects":["equal(instance.cpu.PC, 0xcdef, 'Jumped')", "equal(instance.cpu.SP, 50-2, 'Moved SP')", "equal(instance.ram.get(instance, 256+50), 00, 'Set PC high')", "equal(instance.ram.get(instance, 256+49), 19, 'Set PC low')"]}
	]
	SCENARIOS(opname, opcode, "CALL", scenarios)

def RET(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	scenarios = [
		{"data":[], "setup":["instance.cpu.SP = 48", "instance.cpu.PSW=0x85", "instance.ram.set(instance, 256+50, 0xcd)", "instance.ram.set(instance, 256+49, 0xef)"], "cycles":morecycles, "expects":["equal(instance.cpu.SP, 50, 'Incremented SP')", "equal(instance.cpu.PC, 0xcdef, 'Popped PC')", "equal(instance.cpu.PSW, 0x85, 'Didn\\'t change PSW')"]}
	]
	SCENARIOS(opname, opcode, "RET", scenarios)

def RETI(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	scenarios = [
		{"data":[], "setup":["instance.cpu.SP = 47", "instance.cpu.PSW=0x85", "instance.ram.set(instance, 256+48, 0xab)", "instance.ram.set(instance, 256+50, 0xcd)", "instance.ram.set(instance, 256+49, 0xef)"], "cycles":morecycles, "expects":["equal(instance.cpu.SP, 50, 'Incremented SP')", "equal(instance.cpu.PC, 0xcdef, 'Popped PC')", "equal(instance.cpu.PSW, 0xab, 'Set PSW')"]}
	]
	SCENARIOS(opname, opcode, "RETI", scenarios)

def PUSH(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	reg = args[0]
	source = 0x82
	dest = 0x85
	scenarios = []
	for SP in [48, 0]:
		validation = ["equal(opcode.writeAddress(instance, 16), 256+%s, 'Correct write address')"%SP, "equal(opcode.readAddress(instance, 16), '%s', 'Correct read address')"%reg, "equal(opcode.readValue(instance, 16), %s, 'Correct read value')"%source, "equal(opcode.readOrigWriteValue(instance, 16), %s, 'Correct dest value')"%dest]
		scenarios.append({"data":[], "setup":["instance.cpu.SP = %s"%SP, "instance.cpu.%s=%s"%(reg,source), "instance.ram.set(instance, 256+%s, %s)"%(SP,dest) ], "validation":validation, "cycles":morecycles, "expects":["equal(instance.cpu.SP, %s, 'Decremented SP')"%((SP+256-1)%256), "equal(instance.ram.get(instance, 256+%s), %s, 'Pushed %s')"%(SP, source, reg), "equal(instance.cpu.%s, %s, 'Didn\\'t change %s')"%(reg,source,reg)]})
	
	SCENARIOS(opname, opcode, reg, scenarios)
	
def POP(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	reg = args[0]
	source = 0x82
	dest = 0x85
	scenarios = []
	for SP in [48, 255]:
		validation = ["equal(opcode.readAddress(instance, 16), 256+%s, 'Correct read address')"%((SP+1)%256), "equal(opcode.writeAddress(instance, 16), '%s', 'Correct write address')"%reg, "equal(opcode.readValue(instance, 16), %s, 'Correct read value')"%source, "equal(opcode.readOrigWriteValue(instance, 16), %s, 'Correct dest value')"%dest]
		scenarios.append({"data":[], "setup":["instance.cpu.SP = %s"%SP, "instance.cpu.%s=%s"%(reg,dest), "instance.ram.set(instance, 256+%s, %s)"%((SP+1)%256, source)], "validation":validation, "cycles":morecycles, "expects":["equal(instance.cpu.SP, %s, 'Incremented SP')"%((SP+1)%256), "equal(instance.ram.get(instance, 256+%s), %s, 'Didn\\'t change source stack')"%((SP+1)%256, source), "equal(instance.cpu.%s, %s, 'Popped %s')"%(reg,source,reg)]})
	SCENARIOS(opname, opcode, reg, scenarios)

def SET1(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	if opname == "SET1":
		shouldbe = 1
		fullname = "SET"
	if opname == "CLR1":
		shouldbe = 0
		fullname = "CLR"
	for bit in range(0,8):
		scenarios=[]
		bitmask = 2**bit
		if shouldbe == 0:
			bitmask = 255 - bitmask
		opcode = ("%x"%(bit*2 + (1-shouldbe))) + opcode[1]
		for dp in [0, 1]:
			ram = 8 if dp==0 else 8+256
			for source in [0, 255]:
				validation = ["equal(opcode.nextLocation(instance, 16), 16 + 2, 'Correct next location')", "equal(opcode.readAddress(instance, 16), %s, 'Correct read address')"%ram, "equal(opcode.writeAddress(instance, 16), %s, 'Correct write address')"%ram, "equal(opcode.readValue(instance, 16), %s, 'Correct read value')"%source, "equal(opcode.readOrigWriteValue(instance, 16), %s, 'Correct dest value')"%source]
				name = fullname+str(bit+1)+" P"+str(dp)+" Source "+str(source)
				target = source | bitmask if shouldbe else source & bitmask
				scenarios.append({"data":[8], "setup":["instance.cpu.setPSW(instance,SPC700js.consts.PSW_P,%s)"%dp, "instance.ram.set(instance, %s, %s)"%(ram, source)], "validation":validation, "cycles":morecycles, "expects":["equal(instance.ram.get(instance, %s), %s, '%s')"%(ram, target, name)]})
		SCENARIOS(opname, opcode, fullname+str(bit+1), scenarios)
CLR1=SET1

def TSET1(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	if opname == 'TSET1':
		shouldbe = 1
		fullname = "TSET"
	if opname == 'TCLR1':
		shouldbe = 0
		fullname = "TCLR"
	scenarios = []
	for A in [0, 255]:
		for R in [0, 255]:
			name = "R(%s) vs A(%s)"%(R,A)
			n = 1 if R>127 else 0
			z = 1 if R==0 else 0
			dest = R | A if shouldbe else R & (255-A)
			validation = ["equal(opcode.nextLocation(instance, 16), 16 + 3, 'Correct next location')", "equal(opcode.readAddress(instance, 16), 0x1234, 'Correct read address')", "equal(opcode.writeAddress(instance, 16), 0x1234, 'Correct write address')", "equal(opcode.readValue(instance, 16), %s, 'Correct read value')"%R, "equal(opcode.readOrigWriteValue(instance, 16), %s, 'Correct dest value')"%R]
			scenarios.append({"data":[0x34, 0x12], "setup":["instance.cpu.A=%s"%A, "instance.ram.set(instance, 0x1234, %s)"%R], "validation":validation, "cycles":morecycles, "expects":["equal(instance.ram.get(instance, 0x1234), %s, '%s - Set ram correctly')"%(dest, name), "equal(instance.cpu.A, %s, 'Didn\\'t change A')"%A, "equal(instance.cpu.getPSW(instance, SPC700js.consts.PSW_N), %s, '%s - Correct N flag')"%(n, name), "equal(instance.cpu.getPSW(instance, SPC700js.consts.PSW_Z), %s, '%s - Correct Z flag')"%(z, name)]})
	SCENARIOS(opname, opcode, opname, scenarios)
TCLR1=TSET1


def CBITS(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	shouldbe = 1
	if len(args)>2 and args[1] == '/mem':
		shouldbe = 0
	opname = opname if shouldbe else "~"+opname
	opname = opname+"C" if opname == 'MOV1' and args[0]=='mem' else opname

	ldestc = {
		"AND1":lambda c,r:c&r,
		"~AND1":lambda c,r:c&(1-r),
		"OR1":lambda c,r:c|r,
		"~OR1":lambda c,r:c|(1-r),
		"EOR1":lambda c,r:c^r,
		"NOT1":lambda c,r:c,
		"NOTC":lambda c,r:1-c,
		"MOV1":lambda c,r:r,
		"MOV1C":lambda c,r:c
	}[opname]

	scenarios = []
	for bit in range(0,8):
		for R in [0, 1]:
			for C in [0, 1]:
				data = 4062 + (bit << 13)
				source = 1 << bit
				if R == 0:
					source = 255 - source
				dest = source
				if opname == 'NOT1':
					dest = 0 if R==1 else 255
				if opname == 'MOV1C':		# mov1 from C to mem
					if R == 1 and C == 0:
						dest = 0
					if R == 0 and C == 1:
						dest = 255
				destc = 1 if ldestc(C,R) else 0
				name = "%s B[%s] R[%s] C[%s]"%(opname, bit+1, R, C)
				if opname == 'NOT1':
					validation = ["equal(opcode.nextLocation(instance, 16), 16 + 3, 'Correct next location')", "equal(opcode.readAddress(instance, 16), 4062, 'Correct read address')", "equal(opcode.writeAddress(instance, 16), 4062, 'Correct write address')"]
					validation.append("equal(opcode.readValue(instance, 16), %s, 'Correct read value')"%R)
					validation.append("equal(opcode.readOrigWriteValue(instance, 16), %s, 'Correct orig dest value')"%R)
				elif opname == 'NOTC':
					validation = ["equal(opcode.nextLocation(instance, 16), 16 + 1, 'Correct next location')", "equal(opcode.readAddress(instance, 16), 'C', 'Correct read address')", "equal(opcode.writeAddress(instance, 16), 'C', 'Correct write address')"]
					validation.append("equal(opcode.readValue(instance, 16), %s, 'Correct read value')"%C)
					validation.append("equal(opcode.readOrigWriteValue(instance, 16), %s, 'Correct orig dest value')"%C)
				elif opname == 'MOV1C':
					validation = ["equal(opcode.nextLocation(instance, 16), 16 + 3, 'Correct next location')", "equal(opcode.readAddress(instance, 16), 'C', 'Correct read address')", "equal(opcode.writeAddress(instance, 16), 4062, 'Correct write address')"]
					validation.append("equal(opcode.readValue(instance, 16), %s, 'Correct read value')"%C)
					validation.append("equal(opcode.readOrigWriteValue(instance, 16), %s, 'Correct orig dest value')"%R)
				else:
					validation = ["equal(opcode.nextLocation(instance, 16), 16 + 3, 'Correct next location')", "equal(opcode.readAddress(instance, 16), 4062, 'Correct read address')", "equal(opcode.writeAddress(instance, 16), 'C', 'Correct write address')"]
					validation.append("equal(opcode.readValue(instance, 16), %s, 'Correct read value')"%R)
					validation.append("equal(opcode.readOrigWriteValue(instance, 16), %s, 'Correct orig dest value')"%C)

				scenarios.append({"data":[data & 0xff, (data & 0xff00)>>8], "setup":["instance.ram.set(instance, 4062, %s)"%source, "instance.cpu.setPSW(instance, SPC700js.consts.PSW_C, %s)"%C], "validation":validation, "cycles":morecycles, "expects":["equal(instance.ram.get(instance, 4062), %s, '%s - Correct destination')"%(dest,name), "equal(instance.cpu.getPSW(instance, SPC700js.consts.PSW_C), %s, '%s - Correct C')"%(destc, name)]})
	SCENARIOS(opname, opcode, opname, scenarios)
AND1=OR1=EOR1=NOT1=MOV1=NOTC=CBITS

def PSWBITS(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	flags = [opname[-1]]
	if flags[0] == 'V':
		flags=['V','H']
	if opname[0:-1] == 'CLR' or opname[0] == 'D':
		shouldbe = 0
	if opname[0:-1] == 'SET' or opname[0] == 'E':
		shouldbe = 1
	scenarios = []
	for S in [0,1]:
		name="%s from %s"%(opname, S)
		setups = []
		expects = []
		for F in flags:
			setups.append("instance.cpu.setPSW(instance, SPC700js.consts.PSW_%s, %s)"%(F,S))
			expects.append("equal(instance.cpu.getPSW(instance, SPC700js.consts.PSW_%s),%s,'%s set %s flag correctly')"%(F,shouldbe,name,F))
		scenarios.append({"data":[], "setup":setups, "expects":expects, "cycles":morecycles})
	SCENARIOS(opname, opcode, opname, scenarios)
CLRC=SETC=CLRV=CLRP=SETP=EI=DI=PSWBITS

def NOP(opname, args, opcode, bytes, lesscycles, morecycles, flags):
	scenarios = [{"data":[], "setup":[], "expects":[], "cycles":morecycles}]
	SCENARIOS(opname, opcode, opname, scenarios)




opnameOrder = []
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
	lesscycles=line[40:46].strip().split('/')[0]
	lesscycles=int(lesscycles) if len(lesscycles)>0 else 0
	morecycles=line[40:46].strip().split('/')[-1]
	morecycles=int(morecycles) if len(morecycles)>0 else 0
	flags=line[48:56].strip()
	comments=line[58:].strip()
	
	argsplit=[arg.strip() for arg in args.split(',')]

	if len(name)<1:
		continue
	
	if name in globals():
		globals()[name](name,argsplit,opcode, bytes, lesscycles, morecycles, flags)
	if name in modules.keys() and name not in opnameOrder:
		opnameOrder.append(name)

for opname in opnameOrder:
	module(opname)
	for test in modules[opname].keys():
		print('test("%s", function() {%s});'%(test, modules[opname][test]))
