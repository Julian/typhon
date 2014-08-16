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

from typhon.errors import Refused
from typhon.objects.constants import BoolObject, NullObject, wrapBool
from typhon.objects.root import Object


class CharObject(Object):

    def __init__(self, c):
        self._c = c[0]

    def repr(self):
        return "'%s'" % (self._c.encode("utf-8"))

    def recv(self, verb, args):
        if verb == u"asInteger" and len(args) == 0:
            return IntObject(ord(self._c))
        raise Refused(verb, args)


class EqualizerObject(Object):

    def repr(self):
        return "<equalizer>"

    def recv(self, verb, args):
        if verb == u"sameEver":
            if len(args) == 2:
                first, second = args
                return wrapBool(self.sameEver(first, second))
        raise Refused(verb, args)

    def sameEver(self, first, second):
        """
        Determine whether two objects are ever equal.

        This is a complex topic; expect lots of comments.
        """

        # Two identical objects are equal.
        if first is second:
            return True

        # Bools.
        if isinstance(first, BoolObject) and isinstance(second, BoolObject):
            return first.isTrue() == second.isTrue()

        # Chars.
        if isinstance(first, CharObject) and isinstance(second, CharObject):
            return first._c == second._c

        # By default, objects are not equal.
        return False


class IntObject(Object):

    def __init__(self, i):
        self._i = i

    def repr(self):
        return "%d" % self._i

    def recv(self, verb, args):
        if verb == u"add":
            if len(args) == 1:
                other = args[0]
                if isinstance(other, IntObject):
                    return IntObject(self._i + other._i)
        elif verb == u"multiply":
            if len(args) == 1:
                other = args[0]
                if isinstance(other, IntObject):
                    return IntObject(self._i * other._i)
        elif verb == u"negate" and len(args) == 0:
            return IntObject(-self._i)
        elif verb == u"subtract" and len(args) == 1:
            other = args[0]
            if isinstance(other, IntObject):
                return IntObject(self._i - other._i)
        raise Refused(verb, args)


class ConstListObject(Object):

    def __init__(self, l):
        self._l = l

    def repr(self):
        return "[" + ", ".join([obj.repr() for obj in self._l]) + "]"

    def recv(self, verb, args):
        if verb == u"_makeIterator" and len(args) == 0:
            return listIterator(self._l)
        raise Refused(verb, args)


def pairRepr(pair):
    key, value = pair
    return key.repr() + " => " + value.repr()


class ConstMapObject(Object):

    def __init__(self, l):
        self._l = l

    def repr(self):
        return "[" + ", ".join([pairRepr(pair) for pair in self._l]) + "]"

    def recv(self, verb, args):
        raise Refused(verb, args)


class listIterator(Object):

    _index = 0

    def __init__(self, l):
        self._l = l

    def recv(self, verb, args):
        if verb == u"next" and len(args) == 1:
            if self._index < len(self._l):
                rv = [IntObject(self._index), self._l[self._index],
                        NullObject]
                self._index += 1
                return ConstListObject(rv)
            else:
                ej = args[0]
                ej.recv(u"run", [StrObject(u"Iterator exhausted")])
        raise Refused(verb, args)


class StrObject(Object):

    def __init__(self, s):
        self._s = s

    def repr(self):
        return '"%s"' % self._s.encode("utf-8")

    def recv(self, verb, args):
        if verb == u"get":
            if len(args) == 1:
                index = args[0]
                if isinstance(index, IntObject):
                    return CharObject(self._s[index._i])
        elif verb == u"slice" and len(args) == 1:
            index = args[0]
            if isinstance(index, IntObject):
                start = index._i
                if start >= 0:
                    return StrObject(self._s[start:])
        elif verb == u"_makeIterator" and len(args) == 0:
            return listIterator([CharObject(c) for c in self._s])
        raise Refused(verb, args)


class ScriptObject(Object):

    def __init__(self, script, env):
        self._env = env
        self._script = script
        self._methods = {}

        for method in self._script._methods:
            # God *dammit*, RPython.
            from typhon.nodes import Method
            assert isinstance(method, Method)
            assert isinstance(method._verb, unicode)
            self._methods[method._verb] = method

    def repr(self):
        return "<scriptObject>"

    def recv(self, verb, args):
        if verb in self._methods:
            method = self._methods[verb]

            with self._env as env:
                # Set up parameters from arguments.
                if not method._ps.unify(ConstListObject(args), env):
                    raise RuntimeError
                # Run the block.
                rv = method._b.evaluate(env)

            return rv
        raise Refused(verb, args)
