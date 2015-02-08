# Copyright (C) 2014 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from rpython.rlib.jit import jit_debug, unroll_safe
from rpython.rlib.objectmodel import specialize

from typhon.env import Environment
from typhon.errors import Ejecting, UserException
from typhon.objects.collections import unwrapList
from typhon.objects.constants import unwrapBool
from typhon.objects.data import StrObject
from typhon.objects.ejectors import Ejector, throw
from typhon.objects.slots import Binding, FinalSlot

(
    DUP, ROT, POP, SWAP,
    ASSIGN_FRAME, ASSIGN_LOCAL, BIND, BINDSLOT,
    SLOT_FRAME, SLOT_LOCAL, NOUN_FRAME, NOUN_LOCAL,
    BINDING_FRAME, BINDING_LOCAL,
    LIST_PATT,
    LITERAL,
    BINDOBJECT, SCOPE,
    EJECTOR, TRY, UNWIND, END_HANDLER,
    BRANCH, CALL, JUMP,
) = range(25)

ops = {
    "DUP": DUP,
    "ROT": ROT,
    "POP": POP,
    "SWAP": SWAP,
    "ASSIGN_FRAME": ASSIGN_FRAME,
    "ASSIGN_LOCAL": ASSIGN_LOCAL,
    "BIND": BIND,
    "BINDSLOT": BINDSLOT,
    "SLOT_FRAME": SLOT_FRAME,
    "SLOT_LOCAL": SLOT_LOCAL,
    "NOUN_FRAME": NOUN_FRAME,
    "NOUN_LOCAL": NOUN_LOCAL,
    "BINDING_FRAME": BINDING_FRAME,
    "BINDING_LOCAL": BINDING_LOCAL,
    "LIST_PATT": LIST_PATT,
    "LITERAL": LITERAL,
    "BINDOBJECT": BINDOBJECT,
    "SCOPE": SCOPE,
    "EJECTOR": EJECTOR,
    "TRY": TRY,
    "UNWIND": UNWIND,
    "END_HANDLER": END_HANDLER,
    "BRANCH": BRANCH,
    "CALL": CALL,
    "JUMP": JUMP,
}


reverseOps = {v:k for k, v in ops.iteritems()}


class Code(object):
    """
    SmallCaps code object.
    """

    _immutable_ = True
    _immutable_fields_ = ("instructions[*]", "indices[*]", "atoms[*]",
                          "frame[*]", "literals[*]", "locals[*]",
                          "scripts[*]")

    def __init__(self, instructions, atoms, literals, frame, locals, scripts):
        # Copy all of the lists on construction, to satisfy RPython's need for
        # these lists to be immutable.
        self.instructions = [pair[0] for pair in instructions]
        self.indices = [pair[1] for pair in instructions]
        self.atoms = atoms[:]
        self.literals = literals[:]
        self.frame = frame[:]
        self.locals = locals[:]
        self.scripts = scripts[:]

    def dis(self, instruction, index):
        base = "%s %d" % (reverseOps[instruction], index)
        if instruction == CALL:
            base += " (%s)" % self.atoms[index].repr()
        # XXX enabling this requires the JIT to be able to traverse a lot of
        # otherwise-unsafe code. You're free to try to fix it, but you've been
        # warned.
        # elif instruction == LITERAL:
        #     base += " (%s)" % self.literals[index].toString().encode("utf-8")
        elif instruction in (NOUN_FRAME, ASSIGN_FRAME, SLOT_FRAME,
                BINDING_FRAME):
            base += " (%s)" % self.frame[index].encode("utf-8")
        elif instruction in (NOUN_LOCAL, ASSIGN_LOCAL, SLOT_LOCAL,
                BINDING_LOCAL, BIND, BINDSLOT):
            base += " (%s)" % self.locals[index].encode("utf-8")
        return base

    def disAt(self, index):
        instruction = self.instructions[index]
        index = self.indices[index]
        return self.dis(instruction, index)

    def disassemble(self):
        rv = []
        for i, instruction in enumerate(self.instructions):
            index = self.indices[i]
            rv.append("%d: %s" % (i, self.dis(instruction, index)))
        return "\n".join(rv)


class SmallCaps(object):
    """
    A SmallCaps abstract bytecode interpreter.
    """

    _immutable_fields_ = "code"

    def __init__(self, code, scope):
        frame = [(i, scope[key]) for i, key in enumerate(code.frame)]

        self.code = code
        self.env = Environment(frame, len(frame), len(self.code.locals))

        self.valueStack = []
        self.handlerStack = []

    def pop(self):
        return self.valueStack.pop()

    def push(self, value):
        self.valueStack.append(value)

    @unroll_safe
    def runInstruction(self, instruction, pc):
        index = self.code.indices[pc]
        jit_debug(reverseOps[instruction], index, pc)

        if instruction == DUP:
            self.push(self.valueStack[-1])
            return pc + 1
        elif instruction == ROT:
            (self.valueStack[-1],
             self.valueStack[-3],
             self.valueStack[-2]) = (self.valueStack[-3],
                                     self.valueStack[-2],
                                     self.valueStack[-1])
            return pc + 1
        elif instruction == POP:
            self.pop()
            return pc + 1
        elif instruction == SWAP:
            (self.valueStack[-1],
             self.valueStack[-2]) = (self.valueStack[-2],
                                     self.valueStack[-1])
            return pc + 1
        elif instruction == ASSIGN_FRAME:
            value = self.pop()
            slot = self.env.putValueFrame(index, value)
            return pc + 1
        elif instruction == ASSIGN_LOCAL:
            value = self.pop()
            slot = self.env.putValueLocal(index, value)
            return pc + 1
        elif instruction == BIND:
            binding = self.pop()
            self.env.createBindingLocal(index, binding)
            return pc + 1
        elif instruction == BINDSLOT:
            slot = self.pop()
            self.env.createSlotLocal(index, slot)
            return pc + 1
        elif instruction == SLOT_FRAME:
            self.push(self.env.getSlotFrame(index))
            return pc + 1
        elif instruction == SLOT_LOCAL:
            self.push(self.env.getSlotLocal(index))
            return pc + 1
        elif instruction == NOUN_FRAME:
            self.push(self.env.getValueFrame(index))
            return pc + 1
        elif instruction == NOUN_LOCAL:
            self.push(self.env.getValueLocal(index))
            return pc + 1
        elif instruction == BINDING_FRAME:
            self.push(self.env.getBindingFrame(index))
            return pc + 1
        elif instruction == BINDING_LOCAL:
            self.push(self.env.getBindingLocal(index))
            return pc + 1
        elif instruction == LIST_PATT:
            ej = self.pop()
            xs = unwrapList(self.pop())
            if len(xs) < index:
                throw(ej,
                      StrObject(u"Failed list pattern (needed %d, got %d)" %
                          (index, len(xs))))
            while index:
                index -= 1
                self.push(xs[index])
                self.push(ej)
            return pc + 1
        elif instruction == LITERAL:
            self.push(self.code.literals[index])
            return pc + 1
        elif instruction == BINDOBJECT:
            script = self.code.scripts[index]
            closure = [self.pop() for _ in script.closureNames]
            closure.reverse()
            obj = script.makeObject(closure)
            # Make sure that the object has access to itself, if necessary.
            obj.patchSelf(Binding(FinalSlot(obj)))
            self.push(obj)
            return pc + 1
        elif instruction == EJECTOR:
            ej = Ejector()
            self.push(ej)
            self.handlerStack.append(Eject(self, ej, index))
            return pc + 1
        elif instruction == TRY:
            self.handlerStack.append(Catch(self, index))
            return pc + 1
        elif instruction == UNWIND:
            self.handlerStack.append(Unwind(self, index))
            return pc + 1
        elif instruction == END_HANDLER:
            handler = self.handlerStack.pop()
            handler.drop(self, index)
            return pc + 1
        elif instruction == BRANCH:
            cond = unwrapBool(self.pop())
            if cond:
                return pc + 1
            else:
                return index
        elif instruction == CALL:
            atom = self.code.atoms[index]
            args = [self.pop() for _ in range(atom.arity)]
            args.reverse()
            target = self.pop()
            self.push(target.call(atom.verb, args))
            return pc + 1
        elif instruction == JUMP:
            return index
        else:
            raise RuntimeError("Unknown instruction %d" % instruction)

    @unroll_safe
    def run(self):
        # print ">" * 10
        pc = 0
        while pc < len(self.code.instructions):
            instruction = self.code.instructions[pc]
            try:
                # print ">", pc, self.code.dis(instruction,
                #                              self.code.indices[pc])
                jit_debug("Before run")
                pc = self.runInstruction(instruction, pc)
                jit_debug("After run")
                # print "Stack:", self.valueStack
                # if self.handlerStack:
                #     print "Handlers:", self.handlerStack
            except Ejecting as e:
                pc = self.unwindEjector(e)
            except UserException as ue:
                pc = self.unwindEx(ue)
        # If there is a final handler, drop it; it may cause exceptions to
        # propagate or perform some additional stack unwinding.
        if self.handlerStack:
            finalHandler = self.handlerStack.pop()
            finalHandler.drop(self, pc)
        # print "<" * 10

    def unwindEjector(self, ex):
        while self.handlerStack:
            handler = self.handlerStack.pop()
            rv = handler.eject(self, ex)
            if rv != -1:
                return rv
        raise ex

    def unwindEx(self, ex):
        while self.handlerStack:
            handler = self.handlerStack.pop()
            rv = handler.unwind(self, ex)
            if rv != -1:
                return rv
        raise ex


class Handler(object):

    def __repr__(self):
        return self.repr()

    def eject(self, machine, ex):
        return -1

    def unwind(self, machine, ex):
        return -1

    def drop(self, machine, index):
        pass


class Eject(Handler):

    def __init__(self, machine, ejector, index):
        self.valueHeight = len(machine.valueStack)
        self.handlerHeight = len(machine.handlerStack)
        self.ejector = ejector
        self.index = index

    def repr(self):
        return "Eject(%d)" % self.index

    def eject(self, machine, ex):
        if ex.ejector is self.ejector:
            machine.valueStack = machine.valueStack[:self.valueHeight]
            machine.handlerStack = machine.handlerStack[:self.handlerHeight]
            machine.push(ex.value)
            return self.index
        else:
            return -1


class Catch(Handler):

    def __init__(self, machine, index):
        self.valueHeight = len(machine.valueStack)
        self.handlerHeight = len(machine.handlerStack)
        self.index = index

    def repr(self):
        return "Catch(%d)" % self.index

    def unwind(self, machine, ex):
        machine.valueStack = machine.valueStack[:self.valueHeight]
        machine.handlerStack = machine.handlerStack[:self.handlerHeight]
        machine.push(StrObject(u"Uninformative exception"))
        return self.index


class Unwind(Handler):

    def __init__(self, machine, index):
        self.valueHeight = len(machine.valueStack)
        self.handlerHeight = len(machine.handlerStack)
        self.index = index

    def repr(self):
        return "Unwind(%d)" % self.index

    def eject(self, machine, ex):
        rv = self.carryOn(machine)
        machine.handlerStack.append(Rethrower(ex))
        return rv

    def unwind(self, machine, ex):
        rv = self.carryOn(machine)
        machine.handlerStack.append(Rethrower(ex))
        return rv

    def carryOn(self, machine):
        machine.valueStack = machine.valueStack[:self.valueHeight]
        machine.handlerStack = machine.handlerStack[:self.handlerHeight]
        return self.index

    def drop(self, machine, index):
        machine.handlerStack.append(Returner(index))


class Rethrower(Handler):

    @specialize.argtype(1)
    def __init__(self, ex):
        self.ex = ex

    def repr(self):
        return "Rethrower"

    def drop(self, machine, index):
        raise self.ex


class Returner(Handler):

    def __init__(self, index):
        self.index = index

    def repr(self):
        return "Returner"

    def drop(self, machine, index):
        machine.pc = index