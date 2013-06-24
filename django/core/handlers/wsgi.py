from __future__ import unicode_literals

import codecs
import logging
import sys
from io import BytesIO
from threading import Lock

from django import http
from django.core import signals
from django.core.handlers import base
from django.core.urlresolvers import set_script_prefix
from django.utils import datastructures
from django.utils.datastructures import MultiValueDict
from django.utils.encoding import force_str

# For backwards compatibility -- lots of code uses this in the wild!
from django.http.response import REASON_PHRASES as STATUS_CODE_TEXT

logger = logging.getLogger('django.request')


class LimitedStream(object):
    '''
    LimitedStream wraps another stream in order to not allow reading from it
    past specified amount of bytes.
    '''
    def __init__(self, stream, limit, buf_size=64 * 1024 * 1024):
        self.stream = stream
        self.remaining = limit
        self.buffer = b''
        self.buf_size = buf_size

    def _read_limited(self, size=None):
        if size is None or size > self.remaining:
            size = self.remaining
        if size == 0:
            return b''
        result = self.stream.read(size)
        self.remaining -= len(result)
        return result

    def read(self, size=None):
        if size is None:
            result = self.buffer + self._read_limited()
            self.buffer = b''
        elif size < len(self.buffer):
            result = self.buffer[:size]
            self.buffer = self.buffer[size:]
        else: # size >= len(self.buffer)
            result = self.buffer + self._read_limited(size - len(self.buffer))
            self.buffer = b''
        return result

    def readline(self, size=None):
        while b'\n' not in self.buffer and \
              (size is None or len(self.buffer) < size):
            if size:
                # since size is not None here, len(self.buffer) < size
                chunk = self._read_limited(size - len(self.buffer))
            else:
                chunk = self._read_limited()
            if not chunk:
                break
            self.buffer += chunk
        sio = BytesIO(self.buffer)
        if size:
            line = sio.readline(size)
        else:
            line = sio.readline()
        self.buffer = sio.read()
        return line


class WSGIRequest(http.HttpRequest):
    _request_vars_loaded = False

    @property
    def encoding(self):
        return self._encoding

    @encoding.setter
    def encoding(self, val):
        self._encoding = val
        if self._request_vars_loaded:
            self._load_request_vars()

    def __init__(self, environ):
        super(WSGIRequest, self).__init__()

        script_name = base.get_script_name(environ)
        path_info = base.get_path_info(environ)
        if not path_info:
            # Sometimes PATH_INFO exists, but is empty (e.g. accessing
            # the SCRIPT_NAME URL without a trailing slash). We really need to
            # operate as if they'd requested '/'. Not amazingly nice to force
            # the path like this, but should be harmless.
            path_info = '/'
        self.path_info = path_info
        self.path = '%s/%s' % (script_name.rstrip('/'), path_info.lstrip('/'))

        self.environ = environ
        self.META = environ
        self.META['SCRIPT_NAME'] = script_name
        self.META['PATH_INFO'] = path_info

        self.COOKIES = http.parse_cookie(self.environ.get('HTTP_COOKIE', ''))

        self.method = environ['REQUEST_METHOD'].upper()

        content_params = self._parse_content_type(self.META.get('CONTENT_TYPE', ''))[1]
        if 'charset' in content_params:
            try:
                codecs.lookup(content_params['charset'])
            except LookupError:
                pass
            else:
                self.encoding = content_params['charset']

        try:
            content_length = int(self.environ.get('CONTENT_LENGTH'))
        except (ValueError, TypeError):
            content_length = 0
        self._stream = LimitedStream(self.environ['wsgi.input'], content_length)
        self._read_started = False

    def __getattribute__(self, name):
        _request_vars_loaded = super(WSGIRequest, self).__getattribute__('_request_vars_loaded')
        if _request_vars_loaded is False and name in {'GET', 'POST', 'FILES', 'REQUEST'}:
            self._request_vars_loaded = True
            self._load_request_vars()
        return super(WSGIRequest, self).__getattribute__(name)

    def _load_request_vars(self):
        # The WSGI spec says 'QUERY_STRING' may be absent.
        self.GET = http.QueryDict(self.environ.get('QUERY_STRING', ''), encoding=self.encoding)

        # self.POST and self.FILES
        self._load_post_and_files()

        self.REQUEST = datastructures.MergeDict(self.POST, self.GET)

    def _load_post_and_files(self):
        """Populate self.POST and self.FILES if the content-type is a form type"""
        if self.method != 'POST':
            self.POST, self.FILES = http.QueryDict('', encoding=self.encoding), MultiValueDict()
            return
        if self._read_started and not hasattr(self, '_body'):
            self._post_parse_error = True
            self.POST, self.FILES = http.QueryDict(''), MultiValueDict()
            return

        if self.META.get('CONTENT_TYPE', '').startswith('multipart/form-data'):
            if hasattr(self, '_body'):
                # Use already read data
                data = BytesIO(self._body)
            else:
                data = self
            try:
                self.POST, self.FILES = self.parse_file_upload(self.META, data)
            except:
                # An error occured while parsing POST data.
                # Mark that an error occured. This allows self.__repr__ to
                # be explicit about it instead of simply representing an
                # empty POST
                self._post_parse_error = True
                self.POST, self.FILES = http.QueryDict(''), MultiValueDict()
                raise
        elif self.META.get('CONTENT_TYPE', '').startswith('application/x-www-form-urlencoded'):
            self.POST, self.FILES = http.QueryDict(self.body, encoding=self.encoding), MultiValueDict()
        else:
            self.POST, self.FILES = http.QueryDict('', encoding=self.encoding), MultiValueDict()

    def _is_secure(self):
        return 'wsgi.url_scheme' in self.environ and self.environ['wsgi.url_scheme'] == 'https'

    def _parse_content_type(self, ctype):
        """
        Media Types parsing according to RFC 2616, section 3.7.

        Returns the data type and parameters. For example:
        Input: "text/plain; charset=iso-8859-1"
        Output: ('text/plain', {'charset': 'iso-8859-1'})
        """
        content_type, _, params = ctype.partition(';')
        content_params = {}
        for parameter in params.split(';'):
            k, _, v = parameter.strip().partition('=')
            content_params[k] = v
        return content_type, content_params


class WSGIHandler(base.BaseHandler):
    initLock = Lock()
    request_class = WSGIRequest

    def __call__(self, environ, start_response):
        # Set up middleware if needed. We couldn't do this earlier, because
        # settings weren't available.
        if self._request_middleware is None:
            with self.initLock:
                try:
                    # Check that middleware is still uninitialised.
                    if self._request_middleware is None:
                        self.load_middleware()
                except:
                    # Unload whatever middleware we got
                    self._request_middleware = None
                    raise

        set_script_prefix(base.get_script_name(environ))
        signals.request_started.send(sender=self.__class__)
        try:
            request = self.request_class(environ)
        except UnicodeDecodeError:
            logger.warning('Bad Request (UnicodeDecodeError)',
                exc_info=sys.exc_info(),
                extra={
                    'status_code': 400,
                }
            )
            response = http.HttpResponseBadRequest()
        else:
            response = self.get_response(request)

        response._handler_class = self.__class__

        status = '%s %s' % (response.status_code, response.reason_phrase)
        response_headers = [(str(k), str(v)) for k, v in response.items()]
        for c in response.cookies.values():
            response_headers.append((str('Set-Cookie'), str(c.output(header=''))))
        start_response(force_str(status), response_headers)
        return response
