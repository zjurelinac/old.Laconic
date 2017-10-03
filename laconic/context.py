"""Request processing context class and its utilities

TODO: ...

Copyright:  (c) Zvonimir Jurelinac 2017
License:    MIT, see LICENSE for more details
"""

import traceback

from werkzeug.datastructures import Headers

from .exceptions import BaseAPIException, APIContextProcessingError, \
    APIMissingParameterError, APIInvalidParameterError, \
    APIEndpointRuntimeError
from .utilities import _missing, Request, make_context_response


class Context:
    """
    Request handling context, contains the state and all necessary data for
    handling of the received request.
    """

    CONTEXT_CREATED = 1
    CONTEXT_INITIALIZED = 2
    REQUEST_PARSED = 3
    ENDPOINT_DETERMINED = 4
    RESPONSE_GENERATED = 5
    CONTEXT_FINALIZED = 6
    CONTEXT_ERROR = -1

    _actions = {
        CONTEXT_INITIALIZED: '_process_request',
        REQUEST_PARSED: '_determine_endpoint',
        ENDPOINT_DETERMINED: '_dispatch_request',
        CONTEXT_ERROR: '_process_error'
    }

    def __init__(self, app, environ):
        self.state = Context.CONTEXT_CREATED

        self._app = app

        self.environ = environ
        self.request = None
        self.endpoint = None
        self.response = None
        self.response_status = None
        self.exception = None

    # Context manager methods

    def __enter__(self):
        """Initialize request context"""
        self._init_context()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Finalize request context"""
        if exc_type is not None:
            print('An exception in context exit')
            self.state = Context.CONTEXT_ERROR
            self.exception = BaseAPIException.from_exception_data(
                exc_type, exc_val, exc_tb)
            self._app.logger.error(self.exception)
            if self._app.config['DEBUG']:
                self._app.logger.error('\n'.join(traceback.format_tb(exc_tb)))

            self._process_error()

        self._finalize_context()
        return True

    # Public methods for the app to call

    def do_next(self):
        """
        Perform the next step in request handling

        The steps are as follows:
            (0. Create request context  - in __init__)
            (1. Initialize context      - in __enter__)
            2. Parse request
            3. Determine correct endpoint
            4. Dispatch request
            5. Generate response
            (6. Finalize context         - in __exit__)
        """
        while self.state != Context.RESPONSE_GENERATED:
            handler = getattr(self, self._actions[self.state])
            # self._app.logger.info('Doing %s' % handler.__name__)
            yield handler()

    # Internal request-handling methods

    def _init_context(self):
        """
        Initialize the request context by calling `oncontextinit` handlers
        """
        if self.state != Context.CONTEXT_CREATED:
            raise APIContextProcessingError('Didn\'t expect the context to be '
                                            'in state %d.' % self.state)

        self._app.trigger_event('on_context_init', self)
        self.state = Context.CONTEXT_INITIALIZED

    def _process_request(self):
        """
        Parse the incoming request into the `Request` wrapper and
        call `onrequestparsed` handlers
        """
        if self.state != Context.CONTEXT_INITIALIZED:
            raise APIContextProcessingError(
                'Didn\'t expect the context to be in state %d.' % self.state)

        self.request = Request(self.environ)
        self.state = Context.REQUEST_PARSED
        self._app.trigger_event('on_request_parsed', self.request, self)

    def _determine_endpoint(self):
        """
        Determine which endpoint is responsible for serving the request and
        call `onendpointdetermined` handlers
        """
        if self.state != Context.REQUEST_PARSED:
            raise APIContextProcessingError('Didn\'t expect the context to be '
                                            'in state %d.' % self.state)

        self.endpoint = self._app.router.determine_endpoint(self.request.path,
                                                            self.request.method)
        self.state = Context.ENDPOINT_DETERMINED
        self._app.trigger_event('on_endpoint_determined', self.endpoint,
                                self.request, self)

    def _dispatch_request(self):
        """
        Dispatch the request to the responsible endpoint, collect the response
        and call `onrequestdispatched` handlers
        """
        if self.state != Context.ENDPOINT_DETERMINED:
            raise APIContextProcessingError('Didn\'t expect the context to be '
                                            'in state %d.' % self.state)

        endpoint_params = _select_endpoint_params(
            self.endpoint, self, self.endpoint.get_url_params(self.request.path))

        try:
            make_context_response(self, self.endpoint(**endpoint_params))
            self.state = Context.RESPONSE_GENERATED
            self._app.trigger_event('on_response_generated', self.response, self)
        except Exception as exc:
            exc_handler = None

            for handler in self._app.exception_handlers:
                if isinstance(exc, handler.exc_type):
                    exc_handler = handler
                    break

            if exc_handler is not None:
                handler_params = _select_handler_params(exc_handler, self, exc)
                result = (exc_handler(**handler_params) if handler_params
                          else exc_handler(exc, self))
                make_context_response(self, result)
                self.state = Context.RESPONSE_GENERATED
                self._app.trigger_event('on_response_generated', self)
            else:
                self.exception = APIEndpointRuntimeError.from_exception(exc)
                self.state = Context.CONTEXT_ERROR

    def _process_error(self):
        """
        Generate a response from the exception that has occurred during
        processing of the current request
        """
        if self.state != Context.CONTEXT_ERROR:
            raise APIContextProcessingError('Didn\'t expect the context to be '
                                            'in state %d.' % self.state)

        resp_generator = getattr(self.exception, 'as_response')
        self.response = resp_generator(verbose=self._app.config['DEBUG'])
        self.state = Context.RESPONSE_GENERATED
        self._app.trigger_event('on_response_generated', self.response, self)

    def _finalize_context(self):
        """
        Destroy request context (close all used resources) by calling
        'oncontextdestroy' handlers
        """
        if self.state != Context.RESPONSE_GENERATED:
            raise APIContextProcessingError('Didn\'t expect the context to be '
                                            'in state %d.' % self.state)

        self._app.trigger_event('on_context_finalize', self)
        self.state = Context.CONTEXT_FINALIZED


def _select_endpoint_params(endpoint, context, url_params):
    """Return dictionary of all parameter values for the endpoint"""
    params_dict = {}
    for param in endpoint.parameters.values():
        # Special types
        if issubclass(param.type_, Headers):
            params_dict[param.name] = context.request.headers
        elif issubclass(param.type_, Context):
            params_dict[param.name] = context

        else:
            value = (url_params[param.name] if param.location == 'path' else
                     context.request.param[param.name])
            if value is None:
                if param.default is not _missing:
                    value = param.default
                else:
                    raise APIMissingParameterError(
                        'Required parameter `%s` is missing from the request'
                        % param.name)

            try:
                params_dict[param.name] = param.type_(value)
            except Exception as exc:
                raise APIInvalidParameterError(
                    'Request parameter `%s` is invalid: %s' % (param.name, exc))

    return params_dict


def _select_handler_params(handler, context, exception):
    """Return dictionary of all parameter values for an exception handler"""
    params_dict = {}
    for param in handler.parameters.values():
        if issubclass(param.type_, Exception):
            params_dict[param.name] = exception
        elif issubclass(param.type_, Context):
            params_dict[param.name] = context
        else:
            # raise KeyError('Unknown exception handler parameter type: %s' % param.type_)
            pass

    return params_dict
