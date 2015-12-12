#!/usr/bin/env python3
# weigh/lang.py

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
