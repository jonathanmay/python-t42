mem_size = 256
NONEVALID = 999999
SUCCESSOUT = -999999

def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    return type('Enum', (), enums)

operands = enum('INPUT',
               'OUTPUT',
               'ALTERNATIVE',
               'GREATER',
               'SHIFTLEFT',
               'SHIFTRIGHT',
               'XORBITS',
               'ANDBITS',
               'ADD',
               'SUBTRACT',
               'BOOT'
               )
 
instructions = enum('PREFIX',
                   'LOADAVAR',
                   'LOADBVAR',
                   'LOADALIT',
                   'LOADBLIT',
                   'STOREAVAR',
                   'LOADAIND',
                   'STOREBIND',
                   'JUMP',
                   'JUMPFALSE',
                   'EQUALALIT',
                   'ADDALIT',
                   'ADJUST',
                   'CALL',
                   'OPERATE'
                   )

def decode_neg(operand):
    if (operand & 8):
        # Negative number, convert
        return -(((~operand) + 1) & 15)
    else:
        # Positive number
        return operand

def create_neg(operand):
    return ((~operand) + 1) & 15

class Channel:

    def __init__(self, name):
        self.callinginput = None
        self.callingoutput = None
        self.validinput = 0
        self.validoutput = 0
        self.altwait = 0
        self.data = 0
        self.bootpointer = 0
        self.name = name

    def getName(self):
        return self.name

    def input(self, proc):
        if (self.validoutput):
            self.validoutput = 0
            self.callingoutput.awake()
            return self.data
        else:
            self.validinput = 1
            self.callinginput = proc
            return NONEVALID

    def input_boot(self):
        data = program[self.bootpointer]
        self.bootpointer += 1
        return data

    def input_alt(self):
        if (self.validoutput):
            return self.data
        else:
            return NONEVALID

    def clear_alt(self, res):
        if (res==1):
            # Output was accepted
            self.validoutput = 0
            self.altwait = 0
            self.callingoutput.awake()

    def clear_wait(self):
        self.altwait = 0

    def wait_alt(self, proc):
        self.validinput = 1
        self.altwait = 1
        self.callinginput = proc

    def output(self, proc, data):
        self.data = data
        self.callingoutput = proc
        if (self.validinput & (self.altwait==0)):
            self.validinput = 0
            self.callinginput.awake()
            return SUCCESSOUT
        else:
            self.validoutput = 1
            return NONEVALID

class Processor:

    def __init__(self, channels, name):
        self.name = name
        self.channels = channels
        self.memory = []
        for i in range(mem_size):
            self.memory.append(0)
        self.instruction_pointer = 0
        self.workspace_pointer = 0
        self.areg = 0
        self.breg = 0
        self.ready = 0
        self.instruction = 0
        self.function = 0
        self.operand = 0
        self.memory[0] = (instructions.OPERATE << 4) | operands.BOOT

    def suspend(self, event):
        self.ready = 0

    def awake(self):
        self.ready = 1

    def alt(self, chans, proc):
        readychans = []
        inx = 0
        for chan in chans:
            inx = chan.input_alt()
            if (inx != NONEVALID):
                readychans.append(chan)
        if (len(readychans) == 0):
            # We need to wait until one becomes ready
            for chan in chans:
                chan.wait_alt(proc)
            return [NONEVALID, ""]
        elif (len(readychans) == 1):
            # We have just one ready chan
            readychans[0].clear_alt()
            return [inx, readychans[0].getName()]
        else:
            # We have more than one ready chan
            # Need to pick one, just pick first (TODO unfair)
            inx = readychans[0].input_alt()
            readychans[0].clear_alt()
            return [inx, readychans[0].getName()]
            
    def process(self):
        operand = 0
        if (self.ready):
            instruction = self.memory[self.instruction_pointer]
            self.instruction_pointer += 1
            function = (instruction >> 4)
            operand = (instruction & 15) | operand
            if (function == instructions.PREFIX):
                print "PREFIX"
                operand = operand << 4
            else:
                opvalue = decode_neg(operand)
                if (function == instructions.LOADAVAR):
                    print "LOADAVAR " + str(opvalue)
                    self.areg = self.memory[self.workspace_pointer + opvalue]
                elif (function == instructions.LOADBVAR):
                    print "LOADBVAR " + str(opvalue)
                    self.breg = self.memory[self.workspace_pointer + opvalue]
                elif (function == instructions.LOADALIT):
                    print "LOADALIT " + str(opvalue)
                    self.areg = opvalue
                elif (function == instructions.LOADBLIT):
                    print "LOADBLIT " + str(opvalue)
                    self.breg = opvalue
                elif (function == instructions.STOREAVAR):
                    print "STOREAVAR " + str(opvalue)
                    self.memory[self.workspace_pointer + opvalue] = self.areg
                elif (function == instructions.LOADAIND):
                    print "LOADAIND " + str(opvalue)
                    self.areg = self.memory[self.areg + opvalue]
                elif (function == instructions.STOREBIND):
                    print "STOREBIND " + str(opvalue)
                    self.memory[self.areg + opvalue] = self.breg
                elif (function == instructions.JUMP):
                    print "JUMP " + str(opvalue)
                    self.instruction_pointer += opvalue
                elif (function == instructions.JUMPFALSE):
                    print "JUMPFALSE " + str(opvalue)
                    if (self.areg==0):
                        self.instruction_pointer += opvalue
                elif (function == instructions.EQUALALIT):
                    print "EQUALALIT " + str(opvalue)
                    self.areg = (self.areg == opvalue)
                elif (function == instructions.ADDALIT):
                    print "ADDALIT " + str(opvalue)
                    self.areg += opvalue
                elif (function == instructions.ADJUST):
                    print "ADJUST " + str(opvalue)
                    self.workspace_pointer += opvalue
                elif (function == instructions.CALL):
                    print "CALL " + str(opvalue)
                    self.areg = self.instruction_pointer
                    self.instruction_pointer += opvalue
                elif (function == instructions.OPERATE):
                    if (operand == operands.INPUT):
                        print "OPERATE INPUT"
                        inputdata = channels[self.areg].input(self)
                        if (inputdata == NONEVALID):
                            # We are not ready to progress as the channel isn't ready
                            # Therefore we go to sleep
                            self.suspend()
                            # And when we awake, we reissue this instruction, so need to decrement ip
                            self.instruction_pointer -= 1
                        else:
                            self.areg = inputdata
                    elif (operand == operands.OUTPUT):
                        print "OPERATE OUTPUT"
                        outputdata = channels[self.areg].output(self, self.breg)
                        if (outputdata == NONEVALID):
                            # We are not ready to progress as the channel isn't ready
                            # Therefore we go to sleep
                            self.suspend()
                            # When awoken we continue with the next instruction, so no need to decrement ip
                        # Nothing to do in the case of a successful output
                    elif (operand == operands.ALTERNATIVE):
                        print "OPERATE ALTERNATIVE"
                        chans = []
                        if (self.areg & 1):
                            chans.append('0')
                        if (self.areg & 2):
                            chans.append('1')
                        if (self.areg & 4):
                            chans.append('2')
                        if (self.areg & 8):
                            chans.append('3')
                        resultinput = alt(chans, self)
                        if (resultinput[0]==NONEVALID):
                            # No threads are ready, we need to sleep
                            self.suspend()
                            # And then reissue when awoken
                            self.instruction_pointer -= 1
                        else:
                            for chan in self.channels:
                                chan.clear_wait()
                            self.areg = resultinput[0]
                            if (resultinput[1]=='0'):
                                self.instruction_pointer += 0
                            elif (resultinput[1]=='1'):
                                self.instruction_pointer += 1
                            elif (resultinput[1]=='2'):
                                self.instruction_pointer += 2
                            else: #(resultinput[1]=='3'):
                                self.instruction_pointer += 3
                    elif (operand == operands.GREATER):
                        print "OPERATE GREATER"
                        self.areg = self.areg > self.breg
                    elif (operand == operands.SHIFTLEFT):
                        print "OPERATE SHIFTLEFT"
                        self.areg = self.areg << self.breg
                    elif (operand == operands.SHIFTRIGHT):
                        print "OPERATE SHIFTRIGHT"
                        self.areg = self.areg >> self.breg
                    elif (operand == operands.XORBITS):
                        print "OPERATE XORBITS"
                        self.areg = self.areg ^ self.breg
                    elif (operand == operands.ANDBITS):
                        print "OPERATE ANDBITS"
                        self.areg = self.areg & self.breg
                    elif (operand == operands.ADD):
                        print "OPERATE ADD"
                        self.areg = self.areg + self.breg
                    elif (operand == operands.SUBTRACT):
                        print "OPERATE SUBTRACT"
                        self.areg = self.areg - self.breg
                    elif (operand == operands.BOOT):
                        print "OPERATE BOOT"
                        self.workspace_pointer = self.channels[0].input_boot()
                        self.instruction_pointer = 0
                        while (self.instruction_pointer < self.workspace_pointer):
                            self.memory[self.instruction_pointer] = self.channels[0].input_boot()
                            self.instruction_pointer += 1
                        self.instruction_pointer = 0

chan_zero = Channel('0')
chan_one = Channel('1')
chan_two = Channel('2')
chan_three = Channel('3')

channels = [chan_zero, chan_one, chan_two, chan_three]
channels2 = [chan_three, chan_two, chan_one, chan_zero]
p1 = Processor(channels, "1")
p2 = Processor(channels2, "2")
processors = [p1, p2]

program = [4, 
           (instructions.LOADALIT << 4) | 1, 
           (instructions.LOADBLIT << 4) | 2, 
           (instructions.OPERATE << 4) | operands.ADD, 
           (instructions.JUMP << 4) | create_neg(4)]

for processor in processors:
    processor.awake()

while (True):
    for processor in processors:
        processor.process()
