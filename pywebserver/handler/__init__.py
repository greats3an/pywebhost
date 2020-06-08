import logging,socket
from datetime import datetime
from socketserver import StreamRequestHandler,_SocketWriter
from http import HTTPStatus, server , client
from html import escape
from urllib.parse import urlparse,parse_qs,unquote
from io import BufferedIOBase

'''
Essentially static class variables
'''



# The default request version.  This only affects responses up until
# the point where the request line is parsed, so it mainly decides what
# the client gets back when sending a malformed request line.
# Most web servers default to HTTP 0.9, i.e. don't send a status line.
default_request_version = "HTTP/0.9"

class RequestHandler(StreamRequestHandler):
    """
    Modified version of Python's internal HTTP/1.1 Compatiable `BaseHTTPHandler`

    Modifications had been made to prettify the code and as to fit this server

    better
    """
    def __init__(self, request, client_address, server):
        '''The `server`,which is what instantlizes this handler,must have `__handle__` method
        
        which takes 1 argument (for the handler itself) 
        
        and then the server can do whatever it wants to ;)
        '''
        self.logger = logging.getLogger('RequestHandler')

        '''These values are from the server'''
        # The version of the HTTP protocol we support.
        # Set this to HTTP/1.1 to enable automatic keepalive
        self.protocol_version = server.protocol_version
        # Error page formats
        self.error_message_format = server.error_message_format
        
        # hack to maintain backwards compatibility
        self.responses = {
            v: (v.phrase, v.description)
            for v in HTTPStatus.__members__.values()
        }

        super().__init__(request, client_address, server)

    def parse_request(self):
        """Parse a request (internal).

        The request should be stored in self.raw_requestline; the results
        are in self.command, self.path, self.request_version and
        self.headers.

        Return True for success, False for failure; on failure, any relevant
        error response has already been sent back.

        """
        self.command = None  # set in case of error on the first line
        self.request_version = default_request_version
        self.close_connection = True
        requestline = str(self.raw_requestline, 'iso-8859-1')
        requestline = requestline.rstrip('\r\n')
        self.requestline = requestline
        words = requestline.split()
        if len(words) == 0:  # Empty request line?
            return False

        if len(words) >= 3:  # Enough to determine protocol version
            version = words[-1]
            try:
                if not version.startswith('HTTP/'):
                    raise ValueError
                self.base_version_number = version.split('/', 1)[1]
                version_number = self.base_version_number.split(".")
                # RFC 2145 section 3.1 says there can be only one "." and
                #   - major and minor numbers MUST be treated as
                #      separate integers;
                #   - HTTP/2.4 is a lower version than HTTP/2.13, which in
                #      turn is lower than HTTP/12.3;
                #   - Leading zeros MUST be ignored by recipients.
                if len(version_number) != 2:
                    raise ValueError
                version_number = int(version_number[0]), int(version_number[1])
            except (ValueError, IndexError):
                self.send_error(HTTPStatus.BAD_REQUEST,"Bad request version (%r)" % version)
                return False
            if version_number >= (1, 1) and self.protocol_version >= "HTTP/1.1":
                self.close_connection = False
            if version_number >= (2, 0):
                self.send_error(HTTPStatus.HTTP_VERSION_NOT_SUPPORTED,"Invalid HTTP version (%s)" % self.base_version_number)
                return False
            self.request_version = version

        if not 2 <= len(words) <= 3:
            self.send_error( HTTPStatus.BAD_REQUEST,"Bad request syntax (%r)" % requestline)
            return False
        command, path = words[:2]
        if len(words) == 2:
            self.close_connection = True
            if command != 'GET':
                self.send_error(HTTPStatus.BAD_REQUEST,"Bad HTTP/0.9 request type (%r)" % command)
                return False
        self.command, self.raw_path = command, path
        self.scheme, self.netloc, self.path, self.params, self.query, self.fragment = urlparse(self.raw_path)
        self.path = unquote(self.path)
        self.query = parse_qs(self.query) # Decodes query string to a `dict`
        # Decode the URL
        # Examine the headers and look for a Connection directive.
        try:
            self.headers = client.parse_headers(self.rfile,_class=client.HTTPMessage)
        except client.LineTooLong as err:
            self.send_error(
                HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE,
                "Line too long",
                str(err))
            return False
        except client.HTTPException as err:
            self.send_error(
                HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE,
                "Too many headers",
                str(err)
            )
            return False

        conntype = self.headers.get('Connection', "")
        if conntype.lower() == 'close':
            self.close_connection = True
        elif (conntype.lower() == 'keep-alive' and
              self.protocol_version >= "HTTP/1.1"):
            self.close_connection = False
        # Examine the headers and look for an Expect directive
        expect = self.headers.get('Expect', "")
        if (expect.lower() == "100-continue" and
                self.protocol_version >= "HTTP/1.1" and
                self.request_version >= "HTTP/1.1"):
            if not self.handle_expect_100():
                return False
        return True

    def handle_expect_100(self):
        """Decide what to do with an "Expect: 100-continue" header.

        If the client is expecting a 100 Continue response, we must
        respond with either a 100 Continue or a final response before
        waiting for the request body. The default is to always respond
        with a 100 Continue. You can behave differently (for example,
        reject unauthorized requests) by overriding this method.

        This method should either return True (possibly after sending
        a 100 Continue response) or send an error response and return
        False.

        """
        self.send_response_only(HTTPStatus.CONTINUE)
        self.end_headers()
        return True

    def handle_one_request(self):
        """Handle a single HTTP request.

        You normally don't need to override this method; see the class
        __doc__ string for information on how to handle specific HTTP
        commands such as GET and POST.

        """
        try:
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.requestline = ''
                self.request_version = ''
                self.command = ''
                self.send_error(HTTPStatus.REQUEST_URI_TOO_LONG)
                return
            if not self.raw_requestline:
                self.close_connection = True
                return
            if not self.parse_request():
                # An error code has been sent, just exit
                return
            '''Now,ask the server to process the request'''
            self.server.__handle__(request=self)
            self.wfile.flush() #actually send the response if not already done.
        except socket.timeout as e:
            #a read or a write timed out.  Discard this connection
            self.log_error("Request timed out: %r", e)
            self.close_connection = True
            return

    def handle(self):
        """Handle multiple requests if necessary."""
        self.close_connection = True

        self.handle_one_request()
        while not self.close_connection:
            self.handle_one_request()

    def send_error(self, code, message=None, explain=None):
        """Send and log an error reply.

        Arguments are
        * code:    an HTTP error code
                   3 digits
        * message: a simple optional 1 line reason phrase.
                   *( HTAB / SP / VCHAR / %x80-FF )
                   defaults to short entry matching the response code
        * explain: a detailed message defaults to the long entry
                   matching the response code.

        This sends an error response (so it must be called before any
        output has been generated), logs the error, and finally sends
        a piece of HTML explaining the error to the user.

        """

        try:
            shortmsg, longmsg = self.responses[code]
        except KeyError:
            shortmsg, longmsg = '???', '???'
        if message is None:
            message = shortmsg
        if explain is None:
            explain = longmsg
        self.log_error("code %d, message %s", code, message)
        self.send_response(code, message)
        self.send_header('Connection', 'close')

        # Message body is omitted for cases described in:
        #  - RFC7230: 3.3. 1xx, 204(No Content), 304(Not Modified)
        #  - RFC7231: 6.3.6. 205(Reset Content)
        body = None
        if (code >= 200 and
            code not in (HTTPStatus.NO_CONTENT,
                         HTTPStatus.RESET_CONTENT,
                         HTTPStatus.NOT_MODIFIED)):
            # HTML encode to prevent Cross Site Scripting attacks
            # (see bug #1100201)
            content = (self.error_message_format % {
                'code': code,
                'message': escape(message, quote=False),
                'explain': escape(explain, quote=False)
            })
            body = content.encode('UTF-8', 'replace')
            self.send_header("Content-Type", 'text/html;charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
        self.end_headers()

        if self.command != 'HEAD' and body:
            self.wfile.write(body)

    def send_response(self, code, message=None):
        """Add the response header to the headers buffer and log the
        response code.
        """
        self.log_request(code)
        self.send_response_only(code, message)

    def send_response_only(self, code, message=None):
        """Send the response header only."""
        if self.request_version != 'HTTP/0.9':
            if message is None:
                if code in self.responses:
                    message = self.responses[code][0]
                else:
                    message = ''
            if not hasattr(self, '_headers_buffer'):
                self._headers_buffer = []
            self._headers_buffer.append(("%s %d %s\r\n" %(self.protocol_version, code, message)).encode('latin-1', 'strict'))

    def send_header(self, keyword, value):
        """Send a MIME header to the headers buffer."""
        if self.request_version != 'HTTP/0.9':
            if not hasattr(self, '_headers_buffer'):
                self._headers_buffer = []
            self._headers_buffer.append(
                ("%s: %s\r\n" % (keyword, value)).encode('latin-1', 'strict'))

        if keyword.lower() == 'connection':
            if value.lower() == 'close':
                self.close_connection = True
            elif value.lower() == 'keep-alive':
                self.close_connection = False

    def end_headers(self):
        """Send the blank line ending the MIME headers."""
        if self.request_version != 'HTTP/0.9':
            self._headers_buffer.append(b"\r\n")
            self.flush_headers()

    def flush_headers(self):
        if hasattr(self, '_headers_buffer'):
            self.wfile.write(b"".join(self._headers_buffer))
            self._headers_buffer = []

    def log_request(self, code='-'):
        """Log an accepted request.

        This is called by send_response().

        """
        if isinstance(code, HTTPStatus):
            code = code.value
        self.log_message('"%s" %s %s',self.requestline, str(code), self.useragent_string())

    def address_string(self):
        """Return the client address."""
        return self.client_address[0]

    def useragent_string(self):
        """Returns the client UA header,if applicable"""
        return self.headers.get('User-Agent')

    def time_string(self):
        return str(datetime.now())

    def format_log(self,format,*args):
        """
        Formats a logging message

        Takes `format` and `args` which will construct the base message

        ...and adds other componet into the string

        This method CAN be overwritten.This defaults to mimic the

        NGINX Style logging,which looks like this:

            {Client Address} [{Time}] "{Verb} {Path} {HTTP Version}" {Message}
        """
        try:
            return f'{self.address_string()} [{self.time_string()}]' + f'"{self.command} {self.path} {self.base_version_number}" {format % args}'
        except Exception:
            # If an exception ouccred,fallback to another format            
            return f'{self.address_string()} [{self.time_string()}] {format % args}'
    
    def log_error(self, format, *args):
        """Log an error.

        This is called when a request cannot be fulfilled.  By
        default it passes the message on to log_message().

        Arguments are the same as for log_message().
        """
        self.logger.error(self.format_log(format,*args))        

    def log_message(self, format, *args):
        """Log an arbitrary message.

        This is used by all other logging functions.  Override
        it if you have specific logging wishes.

        The first argument, FORMAT, is a format string for the
        message to be logged.  If the format string contains
        any % escapes requiring parameters, they should be
        specified as subsequent arguments (it's just like
        printf!).

        The formats are decided by `format_log`

        """
        self.logger.info(self.format_log(format,*args))
    
    """
    Properties.These funtions do nothing but providing documents
    
    and will be overriden once the `RequestHandler` is initialized
    """
    @property
    def wfile(self) -> BufferedIOBase:return self._wfile
    @wfile.setter
    def wfile(self,v):
        '''`BufferedIOBase` like I/O for writing messages to sockets'''
        self._wfile = v

    @property
    def rfile(self) -> BufferedIOBase:return self._rfile
    @rfile.setter
    def rfile(self,v):
        '''`BufferedIOBase` like I/O for reading messages from sockets'''
        self._rfile = v

    @property
    def headers(self) -> client.HTTPMessage:return self._headers
    @headers.setter
    def headers(self,v):
        '''Contains parsed headers'''
        self._headers = v

import os
__all__ = [i[:-3] for i in os.listdir(os.path.dirname(__file__)) if i[-2:] == 'py' and i != '__init__.py']
from . import *