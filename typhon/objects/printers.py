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

from rpython.rlib.rstring import UnicodeBuilder

from typhon.atoms import getAtom
from typhon.autohelp import autohelp
from typhon.errors import Refused, UserException
from typhon.objects.constants import NullObject
from typhon.objects.data import CharObject, StrObject, unwrapStr
from typhon.objects.refs import resolution
from typhon.objects.root import Object

INDENT_1 = getAtom(u"indent", 1)
LNPRINT_1 = getAtom(u"lnPrint", 1)
PRINT_1 = getAtom(u"print", 1)
PRINTLN_1 = getAtom(u"println", 1)
QUOTE_1 = getAtom(u"quote", 1)


@autohelp
class Printer(Object):
    """
    An object which can be printed to.
    """

    def __init__(self, ub=None, newline=StrObject(u"\n"), context=None):
        self.ub = ub or UnicodeBuilder()
        self.newline = newline
        if context is None:
            self.context = {}
        else:
            self.context = context

    def toString(self):
        return u"<printer>"

    def indent(self, morePrefix):
        return Printer(self.ub, self.newline.call(u"add", [morePrefix]),
                       self.context)

    def println(self, obj):
        self._print(obj)
        self._print(self.newline)

    def lnPrint(self, obj):
        self._print(self.newline)
        self._print(obj)

    def _print(self, item):
        if isinstance(item, StrObject):
            self.ub.append(unwrapStr(item))
        else:
            self.objPrint(item)

    def recv(self, atom, args):
        if atom is PRINT_1:
            item = resolution(args[0])
            self._print(item)
            return NullObject

        if atom is PRINTLN_1:
            item = resolution(args[0])
            self.println(item)
            return NullObject

        if atom is LNPRINT_1:
            item = resolution(args[0])
            self.lnPrint(item)
            return NullObject

        if atom is QUOTE_1:
            item = resolution(args[0])
            if isinstance(item, CharObject) or isinstance(item, StrObject):
                self.ub.append(item.toQuote())
            else:
                self.objPrint(item)
            return NullObject

        if atom is INDENT_1:
            return self.indent(args[0])

        raise Refused(self, atom, args)

    def objPrint(self, item):
        if item in self.context:
            self.ub.append(u"<**CYCLE**>")
            return
        self.context[item] = None
        try:
            item.call(u"_printOn", [self])
        except UserException, e:
            self.ub.append(u"<** %s throws %s when printed**>" % (
                item.toString(), e.error()))
        del self.context[item]

    def printStr(self, s):
        self.ub.append(s)

    def value(self):
        return self.ub.build()


def toString(self):
    try:
        printer = Printer()
        printer.objPrint(self)
        return printer.value()
    except UserException, e:
        return u"<%s (threw exception %s when printed)>" % (
            self.__class__.__name__.decode('utf-8'),
            e.error())
