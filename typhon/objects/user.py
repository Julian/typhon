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

from rpython.rlib.jit import unroll_safe

from typhon.atoms import getAtom
from typhon.autohelp import autohelp
from typhon.errors import Ejecting, Refused, UserException, userError
from typhon.objects.constants import NullObject, unwrapBool, wrapBool
from typhon.objects.collections.lists import ConstList
from typhon.objects.data import StrObject, unwrapStr
from typhon.objects.ejectors import Ejector
from typhon.objects.guards import anyGuard
from typhon.objects.printers import Printer
from typhon.objects.root import Object
from typhon.objects.slots import finalBinding
from typhon.smallcaps.machine import SmallCaps

# XXX AuditionStamp, Audition guard

ASK_1 = getAtom(u"ask", 1)
GETGUARD_1 = getAtom(u"getGuard", 1)
GETOBJECTEXPR_0 = getAtom(u"getObjectExpr", 0)
GETFQN_0 = getAtom(u"getFQN", 0)


@autohelp
class Audition(Object):

    _immutable_fields_ = "fqn", "ast", "guards"
    # Whether the audition is still fresh and usable.
    active = True

    def __init__(self, fqn, ast, guards, cache):
        assert isinstance(fqn, unicode)
        self.fqn = fqn
        self.ast = ast
        self.guards = guards
        self.cache = cache

        self.approvers = []
        self.askedLog = []
        self.guardLog = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.active = False

    def ask(self, auditor):
        if not self.active:
            raise userError(u"Audition is out of scope")

        cached = False

        self.askedLog.append(auditor)
        if auditor in self.cache:
            answer, asked, guards = self.cache[auditor]
            # msg = u"'%s': %s (cached)" % (auditor.toString(),
            #                               u"true" if answer else u"false")
            # debug_print(msg.encode("utf-8"))
            for name, value in guards:
                # We remember what the binding guards for the previous
                # invocation were.
                if self.guards[name] != value:
                    # If any of them have changed, we need to re-audit.
                    # msg = u"Name '%s' is invalid; reauditing" % name
                    # debug_print(msg.encode("utf-8"))
                    break
            else:
                # XXX stopgap: Ignore negative answers in the cache.
                cached = answer

        if cached:
            for a in asked:
                # We remember the other auditors invoked during this
                # audition. Let's re-ask them since not all of them may have
                # cacheable results.
                # msg = u"Re-asking '%s'" % a.toString()
                # debug_print(msg.encode("utf-8"))
                answer = self.ask(a)
            if answer:
                # debug_print("Reapproving from cache")
                self.approvers.append(auditor)
            return answer
        else:
            # This seems a little convoluted, but the idea is that the logs
            # are written to during the course of the audition, and then
            # copied out to the cache afterwards.
            prevlogs = self.askedLog, self.guardLog
            self.askedLog = []
            self.guardLog = []
            try:
                result = unwrapBool(auditor.call(u"audit", [self]))
                if self.guardLog is not None:
                    self.cache[auditor] = (result, self.askedLog[:],
                                           self.guardLog[:])
                    # msg = u"'%s': %s (cached)" % (auditor.toString(),
                    #                               u"true" if result else u"false")
                    # debug_print(msg.encode("utf-8"))
                if result:
                    # debug_print("Approving")
                    self.approvers.append(auditor)
                return result
            finally:
                self.askedLog, self.guardLog = prevlogs

        return False

    def getGuard(self, name):
        if name not in self.guards:
            self.guardLog = None
            raise userError(u'"%s" is not a free variable in %s' %
                            (name, self.fqn))
        answer = self.guards[name]
        if self.guardLog is not None:
            if False:  # DF check
                self.guardLog.append((name, answer))
            else:
                self.guardLog = None
        return answer

    def recv(self, atom, args):
        if atom is ASK_1:
            return wrapBool(self.ask(args[0]))

        if atom is GETGUARD_1:
            return self.getGuard(unwrapStr(args[0]))

        if atom is GETOBJECTEXPR_0:
            return self.ast

        if atom is GETFQN_0:
            return StrObject(self.fqn)

        raise Refused(self, atom, args)


class ScriptObject(Object):
    """
    An object whose behavior depends on a Monte script.
    """

    _immutable_fields_ = "codeScript", "globals[*]", "stamps[*]"

    def toString(self):
        # Easily the worst part of the entire stringifying experience. We must
        # be careful to not recurse here.
        try:
            printer = Printer()
            self.call(u"_printOn", [printer])
            return printer.value()
        except Refused:
            return u"<%s>" % self.codeScript.displayName
        except UserException, e:
            return (u"<%s (threw exception %s when printed)>" %
                    (self.codeScript.displayName, e.error()))

    def printOn(self, printer):
        # Note that the printer is a Monte-level object. Also note that, at
        # this point, we have had a bad day; we did not respond to _printOn/1.
        from typhon.objects.data import StrObject
        printer.call(u"print",
                     [StrObject(u"<%s>" % self.codeScript.displayName)])

    def auditorStamps(self):
        return self.stamps

    def docString(self):
        return self.codeScript.doc

    def respondingAtoms(self):
        # Only do methods for now. Matchers will be dealt with in other ways.
        d = {}
        for atom in self.codeScript.methods.keys():
            d[atom] = self.codeScript.methodDocs.get(atom, None)

        return d

    def recvNamed(self, atom, args, namedArgs):
        method = self.codeScript.lookupMethod(atom)
        if method:
            return self.runMethod(method, args, namedArgs)
        else:
            # No atoms matched, so there's no prebuilt methods. Instead, we'll
            # use our matchers.
            return self.runMatchers(atom, args, namedArgs)

    @unroll_safe
    def runMatchers(self, atom, args, namedArgs):
        message = ConstList([StrObject(atom.verb), ConstList(args),
                             namedArgs])
        for matcher in self.codeScript.getMatchers():
            with Ejector() as ej:
                try:
                    return self.runMatcher(matcher, message, ej)
                except Ejecting as e:
                    if e.ejector is ej:
                        # Looks like unification failed. On to the next
                        # matcher!
                        continue
                    else:
                        # It's not ours, cap'n.
                        raise

        raise Refused(self, atom, args)


class QuietObject(ScriptObject):
    """
    An object without a closure.
    """

    def __init__(self, codeScript, globals, auditors):
        self.codeScript = codeScript
        self.globals = globals

        # The first auditor is our as-auditor, and it can be null.
        if auditors[0] is NullObject:
            auditors = auditors[1:]
        self.auditors = auditors

        # Grab the guards of our globals and send them off for processing.
        if auditors:
            guards = self.getGuards()
            self.stamps = self.codeScript.audit(auditors, guards)[:]
        else:
            self.stamps = []

    def getGuards(self):
        guards = {}
        for name, i in self.codeScript.globalNames.items():
            guards[name] = self.globals[i].call(u"getGuard", [])
        return guards

    @unroll_safe
    def runMethod(self, method, args, namedArgs):
        machine = SmallCaps(method, None, self.globals)
        # print "--- Running", self.displayName, atom, args
        # Push the arguments onto the stack, backwards.
        machine.push(namedArgs)
        for arg in reversed(args):
            machine.push(arg)
            machine.push(NullObject)
        machine.push(namedArgs)
        machine.run()
        return machine.pop()

    def runMatcher(self, code, message, ej):
        machine = SmallCaps(code, None, self.globals)
        machine.push(message)
        machine.push(ej)
        machine.run()
        return machine.pop()


class BusyObject(ScriptObject):
    """
    An object with a closure.
    """

    _immutable_fields_ = "closure[*]",

    def __init__(self, codeScript, globals, closure, auditors):
        self.codeScript = codeScript
        self.globals = globals
        self.closure = closure

        # The first auditor is our as-auditor, so it'll also be the guard. If
        # it's null, then we'll use Any as our guard.
        if auditors[0] is NullObject:
            self.patchSelf(anyGuard)
            auditors = auditors[1:]
        else:
            self.patchSelf(auditors[0])
        self.auditors = auditors

        # Grab the guards of our closure and send them off for processing.
        if auditors:
            guards = self.getGuards()
            self.stamps = self.codeScript.audit(auditors, guards)[:]
        else:
            self.stamps = []

    def getGuards(self):
        guards = {}
        for name, i in self.codeScript.globalNames.items():
            guards[name] = self.globals[i].call(u"getGuard", [])
        for name, i in self.codeScript.closureNames.items():
            guards[name] = self.closure[i].call(u"getGuard", [])
        return guards

    def patchSelf(self, guard):
        selfIndex = self.codeScript.selfIndex()
        if selfIndex != -1:
            self.closure[selfIndex] = finalBinding(self, guard)

    @unroll_safe
    def runMethod(self, method, args, namedArgs):
        machine = SmallCaps(method, self.closure, self.globals)
        # print "--- Running", self.displayName, atom, args
        # Push the arguments onto the stack, backwards.
        machine.push(namedArgs)
        for arg in reversed(args):
            machine.push(arg)
            machine.push(NullObject)
        machine.push(namedArgs)
        machine.run()
        return machine.pop()

    def runMatcher(self, code, message, ej):
        machine = SmallCaps(code, self.closure, self.globals)
        machine.push(message)
        machine.push(ej)
        machine.run()
        return machine.pop()
