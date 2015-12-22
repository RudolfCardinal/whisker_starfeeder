#!/usr/bin/env python
# starfeeder/lang.py

"""
    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

from collections import OrderedDict
import inspect
import re
import sys


# =============================================================================
# Natural sorting, e.g. for COM ports
# =============================================================================
# http://stackoverflow.com/questions/5967500/how-to-correctly-sort-a-string-with-a-number-inside  # noqa

def atoi(text):
    return int(text) if text.isdigit() else text


def natural_keys(text):
    return [atoi(c) for c in re.split('(\d+)', text)]


# =============================================================================
# Number printing, e.g. for parity
# =============================================================================

def trunc_if_integer(n):
    if n == int(n):
        return int(n)
    return n


# =============================================================================
# Class to store last match of compiled regex
# =============================================================================
# Based on http://stackoverflow.com/questions/597476/how-to-concisely-cascade-through-multiple-regex-statements-in-python  # noqa

class CompiledRegexMemory(object):
    def __init__(self):
        self.last_match = None

    def match(self, compiled_regex, text):
        self.last_match = compiled_regex.match(text)
        return self.last_match

    def search(self, compiled_regex, text):
        self.last_match = compiled_regex.search(text)
        return self.last_match

    def group(self, n):
        if not self.last_match:
            return None
        return self.last_match.group(n)


# =============================================================================
# Name of calling class/function, for status messages
# =============================================================================

def get_class_from_frame(fr):
    # http://stackoverflow.com/questions/2203424/python-how-to-retrieve-class-information-from-a-frame-object  # noqa
    args, _, _, value_dict = inspect.getargvalues(fr)
    # we check the first parameter for the frame function is named 'self'
    if len(args) and args[0] == 'self':
        # in that case, 'self' will be referenced in value_dict
        instance = value_dict.get('self', None)
        if instance:
            # return its class
            cls = getattr(instance, '__class__', None)
            if cls:
                return cls.__name__
            return None
    # return None otherwise
    return None


def get_caller_name(back=0):
    """
    Return details about the CALLER OF THE CALLER (plus n calls further back)
    of this function.
    """
    # http://stackoverflow.com/questions/5067604/determine-function-name-from-within-that-function-without-using-traceback  # noqa
    try:
        frame = sys._getframe(back + 2)
    except ValueError:
        # Stack isn't deep enough.
        return '?'
    function_name = frame.f_code.co_name
    class_name = get_class_from_frame(frame)
    if class_name:
        return "{}.{}".format(class_name, function_name)
    return function_name


# =============================================================================
# AttrDict classes
# =============================================================================

class AttrDict(dict):
    # As per http://stackoverflow.com/questions/4984647
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self


class OrderedNamespace(object):
    # http://stackoverflow.com/questions/455059
    # ... modified for init
    def __init__(self, *args):
        super().__setattr__('_odict', OrderedDict(*args))

    def __getattr__(self, key):
        odict = super().__getattribute__('_odict')
        if key in odict:
            return odict[key]
        return super().__getattribute__(key)

    def __setattr__(self, key, val):
        self._odict[key] = val

    @property
    def __dict__(self):
        return self._odict

    def __setstate__(self, state):  # Support copy.copy
        super().__setattr__('_odict', OrderedDict())
        self._odict.update(state)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    # Plus more (RNC):
    def items(self):
        return self.__dict__.items()

    def __repr__(self):
        return ordered_repr(self, self.__dict__.keys())


# =============================================================================
# Repr assistance function
# =============================================================================

def ordered_repr(obj, attrlist):
    """
    Shortcut to make repr() functions ordered.
    Define your repr like this:

        def __repr__(self):
            return ordered_repr(self, ["field1", "field2", "field3"])
    """
    return "<{classname}({kvp})>".format(
        classname=type(obj).__name__,
        kvp=", ".join("{}={}".format(a, repr(getattr(obj, a)))
                      for a in attrlist)
    )


def simple_repr(obj):
    """Even simpler."""
    return "<{classname}({kvp})>".format(
        classname=type(obj).__name__,
        kvp=", ".join("{}={}".format(k, repr(v))
                      for k, v in obj.__dict__.items())
    )
