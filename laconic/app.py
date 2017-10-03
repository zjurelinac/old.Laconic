"""Laconic app class, a WSGI application and a central object of each app.

Laconic app object is a central object of every Laconic REST API (or other
application) which brings together all the views, regions, handlers and
extensions and provides the WSGI interface for the app to run on any of the
Python WSGI application servers.

Copyright:  (c) Zvonimir Jurelinac 2017
License:    MIT, see LICENSE for more details
"""

import functools
import logging
import sys

from .context import Context
from .exceptions import APIInternalServerError
from .routing import ExceptionHandler, Router
from .utilities import AttributeScope, Config, SortedList, make_context_response


class Laconic:
    """
    Laconic application object - implements a WSGI application interface and
    provides everything that is needed for routing, configuration, resource
    management etc. of your app.
    """

    default_config = dict({
        'APP_DEBUG': True,
        'LOG_FILENAME': 'laconic.log',
        'HTTP_AUTO_OPTIONS_RESPONSE': True,
    })

    POSSIBLE_EVENTS = ['on_app_created',            # No extra hook arguments
                       'on_context_init',           # Hook args: context
                       'on_request_parsed',         # Hook args: request, context
                       'on_endpoint_determined',    # Hook args: endpoint, request, context
                       'on_response_generated',     # Hook args: response, context
                       'on_context_finalize']       # Hook args: context

    EVENT_PRIO_MIN = -1
    EVENT_PRIO_MAX = 100

    def __init__(self, name, config=None, logger=None, routes=None, route_attrs=None):
        self.name = name
        self.config = Config(self.default_config, **(config or {}))
        self.logger = logger or self._create_logger()
        self.resources = object()

        self.router = Router()
        self.route_attrs = AttributeScope(route_attrs)

        if routes is not None:
            self.add_routes(routes)

        self.exception_handlers = []
        self.event_hooks = {k: SortedList() for k in Laconic.POSSIBLE_EVENTS}

        if self.config['HTTP_AUTO_OPTIONS_RESPONSE']:
            self.add_event_hook('on_endpoint_determined',
                                self._process_http_options, -1)

    # Public API-building routes

    def add_route(self, url_rule, endpoint, methods=None, attrs=None):
        """Add a route and its endpoint to the application"""
        if methods is None:
            methods = ['GET']

        if self.config['HTTP_AUTO_OPTIONS_RESPONSE'] and 'OPTIONS' not in methods:
            methods.append('OPTIONS')

        if attrs is not None:
            attrs.parent = self.route_attrs

        self.router.add_rule(url_rule, endpoint, methods, attrs)

    def add_routes(self, routes):
        """Add a list of routes to the app"""
        for url_rule, endpoint, methods, attrs in routes:
            self.add_route(url_rule, endpoint, methods, attrs)

    def add_region(self, region):
        """Add an API region to the app"""
        # TODO: Implement

    def add_exception_handler(self, exc_type, handler):
        """Add an exception handler to handle all runtime exceptions of a given
        type or subtype"""
        self.exception_handlers.append(ExceptionHandler(exc_type, handler))
        self.exception_handlers.sort()

    def add_exception_handlers(self, exc_handlers):
        """Add a list of exception handlers to the app"""
        for exc_type, handler in exc_handlers:
            self.add_exception_handler(exc_type, handler)

    def add_event_hook(self, event, hook, priority=1):
        """Add an event hook for a specific event"""
        if event not in Laconic.POSSIBLE_EVENTS:
            raise KeyError('Unknown event type `%s`, cannot register a hook '
                           'for it' % event)

        if priority < Laconic.EVENT_PRIO_MIN:
            priority = Laconic.EVENT_PRIO_MIN
        elif priority > Laconic.EVENT_PRIO_MAX:
            priority = Laconic.EVENT_PRIO_MAX

        self.event_hooks[event].add(priority, hook)

    def trigger_event(self, event, *args):
        """Trigger an event and call all the hooks defined for it"""
        if event not in Laconic.POSSIBLE_EVENTS:
            raise KeyError('Unknown event type `%s`, cannot trigger it' % event)

        for hook in self.event_hooks[event]:
            hook(*args)

    # Decorators

    def route(self, url_rule, methods=None, attrs=None):
        """
        Decorator for defining application routes, shortcut to `app.add_route`
        """
        def _decorator(func):
            self.add_route(url_rule, func, methods, attrs)
            @functools.wraps(func)
            def _decorated(*args, **kwargs):
                func(*args, **kwargs)
            return _decorated
        return _decorator

    def exception(self, exc_type):
        """
        Decorator for defining exception handlers, shortcut to
        `app.add_exception_handler`
        """
        def _decorator(func):
            self.add_exception_handler(exc_type, func)

            @functools.wraps(func)
            def _decorated(*args, **kwargs):
                func(*args, **kwargs)
            return _decorated
        return _decorator

    def event_hook(self, event, priority=1):
        """
        Decorator for defining event hooks, shortcut to `app.add_event_hook`
        """
        def _decorator(func):
            self.add_event_hook(event, func, priority)

            @functools.wraps(func)
            def _decorated(*args, **kwargs):
                func(*args, **kwargs)
            return _decorated
        return _decorator

    # Internal operations

    def _create_logger(self):
        """
        Create an application-specific logger
        """
        logger = logging.getLogger(self.name)

        if self.config['DEBUG']:
            logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter('[%(asctime)s] '
                                          '<%(module)s/%(funcName)s '
                                          '(%(filename)s:%(lineno)s)> => '
                                          '%(levelname)s :: %(message)s')
            handler = logging.StreamHandler(sys.stdout)
        else:
            logger.setLevel(logging.WARNING)
            formatter = logging.Formatter('[%(asctime)s] <%(module)s> => '
                                          '%(levelname)s :: %(message)s')
            handler = logging.FileHandler(self.config['LOG_FILENAME'])
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def _process_http_options(self, endpoint, request, context):
        """
        Process HTTP OPTIONS requests, via event hooks
        """
        if request.method != 'OPTIONS':
            return

        available_methods = self.router.get_available_methods(context.request.path)
        make_context_response(context, '', headers=[('Allow', ','.join(available_methods))])
        context.state = Context.RESPONSE_GENERATED

    # WSGI protocol

    def __call__(self, environ, start_response):
        """
        A shortcut for accessing the WSGI application
        """
        return self.application(environ, start_response)

    def application(self, environ, start_response):
        """
        A WSGI application callable
        """

        self.logger.info('Application object created, WSGI app started')
        self.trigger_event('on_app_created')
        self.logger.info('Started request handling')

        try:
            with Context(self, environ) as context:
                for _ in context.do_next():
                    pass
            return context.response(environ, start_response)
        except Exception as exc:
            self.logger.error(exc)
            return (APIInternalServerError(
                    'An unexpected internal server error occured')
                    .as_response(verbose=self.config['DEBUG'])
                    (environ, start_response))

    # Builtin development WSGI server -werkzeug

    def run(self, host='localhost', port=8080):
        """
        Run the app on a development WSGI server
        """
        try:
            from werkzeug.serving import run_simple
        except ImportError:
            print('Could not find werkzeug package, aborting')
            sys.exit(1)

        run_simple(host, port, self.application, use_reloader=True)
