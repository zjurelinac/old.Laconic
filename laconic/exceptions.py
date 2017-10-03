"""Laconic framework exceptions

TODO: ...


Copyright:  (c) Zvonimir Jurelinac 2017
License:    MIT, see LICENSE for more details
"""

from werkzeug.exceptions import HTTPException
from werkzeug.http import HTTP_STATUS_CODES

from .utilities import Response, make_json, make_exception_name


class BaseAPIException(Exception):
    """Baseclass for all East framework exceptions.

    TODO: What's specific about it?

    TODO: Describe attributes and methods.
    """

    name = None
    description = None
    status_code = None

    def __init__(self, description, status_code=None, name=None, data=None):
        Exception.__init__(self)

        self.description = description or self.description
        self.status_code = status_code or self.status_code
        self.name = name or self.name or make_exception_name(self)
        self.data = data

    def as_json(self, verbose=False):
        """Return JSON representation of the exception

        TODO: Explain return format and verbose argument
        """
        repr_dict = {'description': self.description,
                     'status_code': self.status_code,
                     'name': self.name}
        if verbose:
            repr_dict.update(data=self.data)
        return make_json(repr_dict)

    def as_response(self, verbose=False):
        """Return a Response object with the exception info

        TODO: Explain response format
        """
        return Response(self.as_json(verbose), status=self.status_code,
                        content_type='application/json')

    @property
    def status(self):
        """Exception HTTP status - ### Reason (ex. 400 Bad Request)"""
        return '%s %s' % (self.status_code, HTTP_STATUS_CODES[self.status_code])

    @classmethod
    def from_exception(cls, exception):
        """Transform another exception into a BaseAPIException

        TODO: Explain what it does
        """
        if isinstance(exception, BaseAPIException):
            return exception

        if isinstance(exception, HTTPException):
            description = exception.description
            status_code = exception.code
        else:
            description = str(exception)
            status_code = 500
        exc_type = type('API' + exception.__class__.__name__,
                        (cls, exception.__class__), {})
        exc = exc_type(description, status_code)
        exc.__traceback__ = exception.__traceback__
        return exc

    @classmethod
    def from_exception_data(cls, exc_type, exc_val, exc_tb):
        """Construct a BaseAPIException from caught exception data

        TODO: Explain what it does
        """
        if issubclass(exc_type, BaseAPIException):
            return exc_val
        else:
            if issubclass(exc_type, HTTPException):
                description = exc_val.description
                status_code = exc_val.code
            else:
                description = str(exc_val)
                status_code = 500

            new_exc_type = type('API' + exc_type.__name__, (cls, exc_type), {})
            new_exc = new_exc_type(description, status_code)
            new_exc.__traceback__ = exc_tb
            return new_exc

    def __str__(self):
        code = self.status_code if self.status_code is not None else '???'
        return '<%s %s>: %s' % (code, self.name, self.description)

    def __repr__(self):
        code = self.status_code if self.status_code is not None else '???'
        return '<%s %s>: %s' % (code, self.__class__.__name__, self.description)


# Basic API exceptions

class APIBadRequestError(BaseAPIException):
    """Base exception for all bad request errors"""
    name = 'Bad Request'
    status_code = 400


class APIMethodNotAllowedError(BaseAPIException):
    """Request method is not allowed for this endpoint"""
    name = 'Method Not Allowed'
    status_code = 405

    def __init__(self, description, status_code=None, name=None, data=None,
                 valid_methods=None):
        BaseAPIException.__init__(description, status_code, name, data)
        self.valid_methods = valid_methods or []

    def as_response(self, verbose=False):
        return Response(self.as_json(verbose), status=self.status_code,
                        content_type='application/json',
                        headers=[('Allow', ', '.join(self.valid_methods))])


class APIDoesNotExistError(BaseAPIException):
    """Requested resource does not exist"""
    name = 'Does Not Exist'
    status_code = 404


# Specific API exception

class APIInvalidParameterError(APIBadRequestError):
    """Request parameter is invalid (wrong type, format or doesn't satisfy constraints)."""
    name = 'Invalid Request Parameter'


class APIMissingParameterError(APIBadRequestError):
    """Required parameter is missing from ther request."""
    name = 'Missing Request Parameter'


class APIEndpointNotFoundError(APIDoesNotExistError):
    """Endpoint for given URL path is not defined."""
    name = 'Endpoint Doesn\'t Exist'


# Internal API exceptions

class APIInternalServerError(BaseAPIException):
    """Baseclass for unexpected internal errors."""
    name = 'Internal Server Error'
    description = 'The server encountered an internal error and was unable to ' \
                  'complete the request'
    status_code = 500


class APIContextProcessingError(APIInternalServerError):
    """Unexpected error while processing the request context."""
    name = 'Context Processing Error'


class APIEndpointDefinitionError(APIInternalServerError):
    """Endpoint improperly defined and cannot be added to the API."""
    name = 'Endpoint Definition Error'


class APIEndpointRuntimeError(APIInternalServerError):
    """Wrapper for errors that occurred while running the endpoint function."""
    name = 'Endpoint Runtime Error'
