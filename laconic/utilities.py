"""
    east.utilities
    ==============
    Contains various utility data structures, classes and functions.

    :copyright: (c) Zvonimir Jurelinac 2017
    :license: MIT, see LICENSE for more details
"""

import bisect
import json
import re

from werkzeug.wrappers import BaseRequest, AcceptMixin, ETagRequestMixin, \
    AuthorizationMixin, CommonRequestDescriptorsMixin, \
    BaseResponse, CommonResponseDescriptorsMixin, \
    ETagResponseMixin


# Utility constants

_missing = object()  # A sentinel value representing missing cache


# HTTP data structures

class Request(BaseRequest, CommonRequestDescriptorsMixin, ETagRequestMixin,
              AuthorizationMixin, AcceptMixin):
    """
    WSGI request wrapper object, contains data about the received request.

    Inherits from werkzeug.wrappers.BaseRequest and various mixins.
    """

    @property
    def is_json(self):
        """
        Test if the request carries JSON data (by looking at the
        `Content-Type` HTTP header)
        """
        return (self.mimetype == 'application/json') or \
               (self.mimetype.startswith('application/') and
                self.mimetype.endswith('+json'))

    @property
    def json(self):
        """
        Parse the JSON request data and return it.

        If the request doesn't contain JSON data, it will return `None`.
        """

        json_data = getattr(self, '_cached_json', _missing)
        if json_data is not _missing:
            return json_data

        request_charset = self.mimetype_params.get('charset')
        try:
            if request_charset is not None:
                json_data = json.loads(self.get_data(as_text=True),
                                       encoding=request_charset)
            else:
                json_data = json.loads(self.get_data(as_text=True))
            self._cached_json = json_data
            return json_data
        except ValueError:
            pass

    @property
    def param(self):
        """
        Combined dictionary containing all request parameters except headers
        """
        if not hasattr(self, '_param'):
            locations = [self.args, self.cookies]
            if self.method in ('POST', 'PUT', 'PATCH'):
                locations = [self.json, self.form, self.files] + locations
            self._param = CombinedDict(locations)
        return self._param


class Response(BaseResponse, CommonResponseDescriptorsMixin, ETagResponseMixin):
    """
    WSGI response wrapper object, contains data about the generated response.

    Inherits from werkzeug.wrappers.BaseResponse and various mixins.
    """


# Utility data structures

class Config(dict):
    """
    Config dict - contains app configuration options. Difference from dict -
    when an item isn't present, won't raise a KeyError, but will return None.
    """

    def __missing__(self, key):
        return None


class AttributeScope:
    """
    Nested attribute scope - provides a dict-like interface, with the difference
    that an element not present in this scope can be retrieved from the parent
    scope.
    """

    def __init__(self, attrs=None, parent=None):
        self.data = attrs if attrs is not None else {}
        self.parent = parent

    def __getitem__(self, key):
        if key in self.data:
            return self.data
        return self.parent[key] if self.parent is not None else None

    def __setitem__(self, key, value):
        self.data[key] = value

    def __delitem__(self, key):
        del self.data[key]


class SortedList:
    """
    A list of values sorted by their priority and insertion order.
    Not too fast implementation as of yet.
    """

    def __init__(self):
        self.elems = []
        self.counter = 0

    def add(self, priority, value):
        """
        Add an element to the sorted list, which remains sorted afterwards
        """
        bisect.insort(self.elems, (-priority, self.counter, value))
        self.counter += 1

    def remove(self, value):
        """Remove an element from the sorted list"""
        for i, elem in enumerate(self.elems):
            if elem[2] == value:
                del self.elems[i]
                break

    def __iter__(self):
        for elem in self.elems:
            yield elem[2]


class CombinedDict:
    """
    Read-only combined dict which allows retrieval of values from any of the
    contained dicts, in order they were passed into the constructor.
    If the key isn't present, retrieval will return None
    """

    def __init__(self, dicts):
        self.dicts = [d for d in dicts if d is not None]

    def __getitem__(self, key):
        for dct in self.dicts:
            if key in dct:
                return dct[key]

    def __setitem__(self, key, value):
        raise TypeError('Cannot modify contents of a CombinedDict')


# Utility functions

def make_json(data_dict):
    """Return JSON representation of Python `data_dict` dictionary."""
    return json.dumps(data_dict, indent=4, sort_keys=True, separators=(',', ': '))


def make_context_response(context, response_obj, headers=None):
    """Set context response from response_obj, with or without status_code """
    if isinstance(response_obj, tuple) and len(response_obj) == 2 and \
            isinstance(response_obj[1], int):
        context.response = response_obj[0]
        context.response_status = response_obj[1]
    else:
        context.response = response_obj

    if headers is None:
        headers = []

    if not isinstance(context.response, Response):
        if hasattr(context.response, 'as_response'):
            context.response = getattr(context.response, 'as_response')()
        else:
            context.response = Response(str(context.response),
                                        status=context.response_status,
                                        headers=headers)


def make_exception_name(exception):
    """Convert an exception class name to a human-readable name"""
    return ' '.join(filter(lambda x: x not in ('API', 'Exception') and x,
                           re.split(r'((?<=[a-zA-Z])[A-Z][a-z]+)',
                                    exception.__class__.__name__)))


def exc_type_compare(exc_type1, exc_type2):
    """Compare two exception types"""
    if issubclass(exc_type1, exc_type2):
        return -1
    elif issubclass(exc_type2, exc_type1):
        return 1
    else:
        sc_depth1 = len(exc_type1.__mro__)
        sc_depth2 = len(exc_type2.__mro__)

        if sc_depth1 == sc_depth2:
            return -1 if exc_type1.__name__ < exc_type2.__name__ else 1
        else:
            return -1 if sc_depth1 < sc_depth2 else 1
