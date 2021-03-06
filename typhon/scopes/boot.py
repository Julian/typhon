# Copyright (C) 2015 Google Inc. All rights reserved.
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

from typhon.atoms import getAtom
from typhon.autohelp import autohelp
from typhon.env import finalize
from typhon.errors import LoadFailed, Refused, userError
from typhon.importing import evaluateRaise, obtainModuleFromSource
from typhon.nodes import kernelAstStamp
from typhon.objects.auditors import deepFrozenStamp, transparentStamp
from typhon.objects.collections.lists import ConstList
from typhon.objects.collections.maps import ConstMap, monteMap, unwrapMap
from typhon.objects.collections.sets import ConstSet
from typhon.objects.data import StrObject, unwrapBytes, wrapBool, unwrapStr
from typhon.objects.guards import (BoolGuard, BytesGuard, CharGuard,
                                   DoubleGuard, IntGuard, StrGuard, VoidGuard)
from typhon.objects.root import Object, audited, runnable
from typhon.objects.tests import UnitTest

EVALTOPAIR_2 = getAtom(u"evalToPair", 2)
RUN_1 = getAtom(u"run", 1)
RUN_2 = getAtom(u"run", 2)


@runnable(RUN_1, [deepFrozenStamp])
def isList(args):
    return wrapBool(isinstance(args[0], ConstList))


@runnable(RUN_1, [deepFrozenStamp])
def isMap(args):
    return wrapBool(isinstance(args[0], ConstMap))


@runnable(RUN_1, [deepFrozenStamp])
def isSet(args):
    return wrapBool(isinstance(args[0], ConstSet))


def evalToPair(source, envMap, recorder):
    source = unwrapBytes(source)
    environment = {}
    for k, v in unwrapMap(envMap).items():
        environment[unwrapStr(k)] = v

    # *Do* catch this particular exception, as it is not a
    # UserException and thus will kill the process (!!!) if allowed to
    # propagate. ~ C.
    try:
        code, topLocals = obtainModuleFromSource(source, recorder, u"<eval>")
    except LoadFailed:
        raise userError(u"Couldn't load invalid AST")

    # Don't catch user exceptions; on traceback, we'll have a trail
    # auto-added that indicates that the exception came through
    # eval() or whatnot.
    result, newEnv = evaluateRaise([code], environment)
    if newEnv is not None:
        # XXX monteMap()
        d = monteMap()
        for k, vi in topLocals.items():
            d[StrObject(k)] = newEnv.local[vi]
        addendum = ConstMap(d)
        envMap = addendum._or(envMap)
    return result, envMap


@autohelp
@audited.DF
class TyphonEval(Object):

    def __init__(self, recorder):
        self.recorder = recorder

    def recv(self, atom, args):
        if atom is RUN_2:
            return evalToPair(args[0], args[1], self.recorder)[0]
        if atom is EVALTOPAIR_2:
            result, envMap = evalToPair(args[0], args[1], self.recorder)
            return ConstList([result, envMap])

        raise Refused(self, atom, args)


def bootScope(recorder, collectTests):
    return finalize({
        u"isList": isList(),
        u"isMap": isMap(),
        u"isSet": isSet(),
        u"Bool": BoolGuard(),
        u"Bytes": BytesGuard(),
        u"Char": CharGuard(),
        u"Double": DoubleGuard(),
        u"Int": IntGuard(),
        u"Str": StrGuard(),
        u"Void": VoidGuard(),

        u"KernelAstStamp": kernelAstStamp,

        u"DeepFrozenStamp": deepFrozenStamp,
        u"TransparentStamp": transparentStamp,

        u"typhonEval": TyphonEval(recorder),
        u"unittest": UnitTest(u"<boot>", collectTests),
    })
