"""URL routing facilities

TODO: ...

Copyright:  (c) Zvonimir Jurelinac 2017
License:    MIT, see LICENSE for more details
"""

import inspect
import re

from .exceptions import APIEndpointNotFoundError, APIMethodNotAllowedError, \
    APIEndpointDefinitionError
from .utilities import AttributeScope, _missing, exc_type_compare


class Router:
    """
    Request to endpoint router class - determines which endpoint should be
    called for a particular request
    """

    def __init__(self):
        self.endpoints = []

    def add_rule(self, url_rule, endpoint, methods=None, attrs=None):
        """Add an endpoint with a given `url_rule` and a set of `attrs`."""
        self.endpoints.append(Endpoint(url_rule, endpoint, methods, attrs))

    def determine_endpoint(self, url_path, method):
        """
        Return the matching endpoint for a given `url_path`, or raise an
        exception if none is found (or the requested HTTP method is
        unsupported for that endpoint).
        """
        available_methods = set()
        for endpoint in self.endpoints:
            match, method_match = endpoint.match(url_path, method)
            if match and method_match:
                return endpoint
            elif match:
                available_methods.update(endpoint.methods)

        if len(available_methods) > 0:
            raise APIMethodNotAllowedError(
                'HTTP method `%s` is not allowed for this endpoint, perhaps try '
                '[%s]?' % (method, ', '.join(available_methods)),
                valid_methods=available_methods)
        else:
            raise APIEndpointNotFoundError('There is no endpoint defined for '
                                           'the `%s` URL path.' % url_path)

    def get_available_methods(self, url_path):
        """
        Return a list of available HTTP methods registered for a given URL
        """
        available_methods = set()
        for endpoint in self.endpoints:
            match, _ = endpoint.match(url_path)
            if match:
                available_methods.update(endpoint.methods)

        return list(available_methods)


class Endpoint:
    """
    API endpoint class containing description of the endpoint and
    """

    def __init__(self, url_rule, endpoint, methods=None, attrs=None):
        self.name = endpoint.__name__
        self.methods = methods
        self.endpoint = endpoint
        self.url_rule = URLRule(url_rule)
        self.attrs = AttributeScope(attrs)

        signature = inspect.signature(endpoint)

        self.parameters = {k: EndpointParam.from_inspect(v, type_mandatory=True)
                           for k, v in signature.parameters.items()}
        # TODO: What about the result, which conditions must it satisfy?
        # TODO: Pass special variables to the result wrapper
        self.result = EndpointResult(signature.return_annotation)

        for param in self.url_rule.url_params:
            if param not in self.parameters:
                raise APIEndpointDefinitionError(
                    'Parameter `%s`, defined in the URL, is not present in '
                    'endpoint function signature.' % param)
            self.parameters[param].location = 'path'

    def match(self, url_path, method=None):
        """Test if provided `url_path` matches this endpoint URL rule"""
        return (self.url_rule.match(url_path), method in self.methods)

    def get_url_params(self, url_path):
        """Return a dictionary of parameters extracted from the URL path"""
        return self.url_rule.extract_params(url_path)

    def __call__(self, *args, **kwargs):
        return self.result(self.endpoint(*args, **kwargs))


class FunctionParam:
    """
    Generic function parameter object - contains parameter name, type and
    default value (if any)
    """
    def __init__(self, name, type_, default=_missing):
        self.name = name
        self.type_ = type_
        self.default = default

    @classmethod
    def from_inspect(cls, inspect_param, type_mandatory=False):
        """Create an EndpointParam from the inspect.Parameter object"""
        if type_mandatory and inspect_param.annotation is inspect.Signature.empty:
            raise APIEndpointDefinitionError('Type of parameter `%s` is '
                                             'undefined' % inspect_param.name)

        return cls(inspect_param.name, inspect_param.annotation,
                   inspect_param.default if inspect_param.default
                   is not inspect.Signature.empty else _missing)


class EndpointParam(FunctionParam):
    """
    Endpoint parameter object - contains parameter name, type, location,
    default value and documentation.
    """

    def __init__(self, name, type_, default=_missing, location=None):
        super().__init__(name, type_, default)
        self.location = location


class EndpointResult:
    """
    Endpoint result processor - contains a callable
    """

    def __init__(self, processor):
        self.processor = processor
        self.parameters = {}

    def __call__(self, *args, **kwargs):
        return self.processor(*args, **kwargs)


class ExceptionHandler:
    """
    API exception handler class - generates API error response for specific
    exception type
    """

    def __init__(self, exc_type, handler):
        self.exc_type = exc_type
        self.handler = handler
        self.parameters = {k: FunctionParam.from_inspect(v) for k, v
                           in inspect.signature(handler).parameters.items()}

    def __call__(self, *args, **kwargs):
        return self.handler(*args, **kwargs)

    def __eq__(self, other):
        return ((self.exc_type == other.exc_type) and
                (self.handler == other.handler))

    def __lt__(self, other):
        return exc_type_compare(self.exc_type, other.exc_type) < 0


class URLRule:
    """Single URL rule for matching the endpoint from request path variable"""

    TYPE_REGEXES = {'int': r'\-?\d+', 'string': r'[^/]+',
                    'float': r'\-?\d+(\.\d*)?', 'path': r'[^/].?'}

    _split_re = re.compile(r'(<|>|:)')

    def __init__(self, url_rule):
        self.url_params = []
        regex = []
        rule_tokens = self._split_re.split(url_rule)
        i = 0
        try:
            while i < len(rule_tokens):
                if rule_tokens[i] == '<':
                    if (i + 4 >= len(rule_tokens) or rule_tokens[i + 2] != ':'
                            or rule_tokens[i + 4] != '>'):
                        raise ValueError('Malformed URL rule `%s`, missing a '
                                         'part of param definition' % url_rule)
                    regex.append('(?P<%s>%s)' %
                                 (rule_tokens[i + 3],
                                  self.TYPE_REGEXES[rule_tokens[i + 1]]))
                    self.url_params.append(rule_tokens[i + 3])
                    i += 5
                elif rule_tokens[i] in ('>', ':'):
                    raise ValueError('Unexpected character `%s` in the URL '
                                     'rule `%s` ' % (rule_tokens[i], url_rule))
                else:
                    regex.append(re.escape(rule_tokens[i]))
                    i += 1
            self.regex = re.compile(''.join(regex))
        except Exception as exc:
            raise APIEndpointDefinitionError(str(exc))

    def match(self, url_path):
        """Test if given `url_path` matches this URL rule"""
        return self.regex.fullmatch(url_path) is not None

    def extract_params(self, url_path):
        """Extract parameters from a given URL"""
        return self.regex.fullmatch(url_path).groupdict()


class Region:
    """
    API region - a separate section of the application, having its base URL
    and (optionally) specific attributes (authentification and privilege level,
    caching etc.)
    """

    def __init__(self, name, base_url, routes=None, route_attrs=None):
        self.name = name
        self.base_url = base_url
        self.routes = routes or []
        self.route_attrs = AttributeScope(route_attrs)

    def add_route(self):
        # TODO: Implement
        pass

    def add_region(self):
        # TODO: Implement
        pass
