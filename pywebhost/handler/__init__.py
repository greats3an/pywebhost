from http.client import OK, ResponseNotReady
from http.cookies import Morsel, SimpleCookie
import logging,socket
from datetime import datetime
from socketserver import StreamRequestHandler
from http import HTTPStatus,client,cookies
from html import escape
from urllib.parse import urlparse,parse_qs,unquote
from io import BufferedIOBase, IOBase
import time
'''
Essentially static class variables
'''

# The default request version.  This only affects responses up until
# the point where the request line is parsed, so it mainly decides what
# the client gets back when sending a malformed request line.
# Most web servers default to HTTP 0.9, i.e. don't send a status line.
default_request_version = "HTTP/0.9"
default_response_code = OK

_MAXLINE = 65536
_MAXHEADERS = 100
_MAXTIMEOUT = 60
'''Try not to set this value to 0 -- this would cause issuses on some Windows machines'''

class Headers(dict):
    '''Crude implementation of https://www.w3.org/Protocols/rfc2616/rfc2616-sec4.html - HTTP Message Headers'''
    def encode(self):
        return str(self).encode()

    def __str__(self) -> str:
        # formatting the lines
        buffer = []        
        if self.response_line:buffer.append(self.response_line )
        for k,v in self.items():buffer.append('%s: %s' % (k,v))
        str_ = buffer[0] + '\n'.join(buffer[1:]) + '\r\n\r\n'
        
        return str_

    def __init__(self,response_line='') -> None:
        self.response_line = response_line
    
    def add_header_line(self,header_line : bytes):
        if not isinstance(header_line,str):
            header_line = header_line.decode()
        header_line = header_line.strip().split(':',maxsplit=1)
        # trying to decode the headers
        if len(header_line) < 2 : return
        key,value = header_line
        self[key.strip()] = value.strip()
        return key,value

    @staticmethod
    def parse(fp : IOBase):
        """Parses only RFC2822 headers from a file pointer.
        """
        headers = Headers()
        while True:
            line = fp.readline(_MAXLINE + 1)
            if len(line) > _MAXLINE:
                raise client.LineTooLong("header line")
            headers.add_header_line(line)
            if len(headers) > _MAXHEADERS:
                raise client.HTTPException("got more than %d headers" % _MAXHEADERS)
            if line in (b'\r\n', b'\n', b''):
                break      
        return headers
    
    def __getitem__(self, k: str) -> str:
        '''https://www.w3.org/Protocols/rfc2616/rfc2616-sec4.html#sec4.2 - field names are case-insentive'''
        return super().__getitem__(k.lower())
    def __setitem__(self, k: str, v: str) -> None:
        '''https://www.w3.org/Protocols/rfc2616/rfc2616-sec4.html#sec4.2 - field names are case-insentive'''
        super().__setitem__(k.lower(),v)
    def get(self, key : str, default=None):
        return super().get(key.lower(),default)
    
class Request(StreamRequestHandler):
    '''HTTP/1.0 1.1 Request handler - based on `RequestHandler` of `site-package`'''
    wfile : BufferedIOBase
    '''`BufferedIOBase` like I/O for writing messages to sockets'''
    rfile : BufferedIOBase
    '''`BufferedIOBase` like I/O for reading messages from sockets'''
    headers : Headers
    '''Contains parsed headers'''        
    headers_buffer : Headers
    '''The headers to be parsed'''
    cookies : cookies.SimpleCookie
    '''Contains request cookies'''
    cookies_buffer : cookies.SimpleCookie
    '''The cookies to be sent by us'''
    command : str
    '''The request command (GET,POST,etc)'''
    raw_requestline : str
    '''Raw `HTTP` request line of the request'''
    raw_request : socket.socket
    '''Raw TCP socket'''
    close_connection : bool
    '''Whether to preserve the connection (keep-alive one) or not'''
    
    def __init__(self, request, client_address, server):
        '''The `server`,which is what instantlizes this handler,must have `handle` method
        which takes 1 argument (for the handler itself) 
        '''
        self.logger = logging.getLogger('Request')
        '''These values are from the server'''
        # The version of the HTTP protocol we support.
        # Set this to HTTP/1.1 to enable automatic keepalive
        self.protocol_version = server.protocol_version
        # Error page formats
        self.format_error_message = server.format_error_message
        # hack to maintain backwards compatibility
        self.responses = {
            v: (v.phrase, v.description)
            for v in HTTPStatus.__members__.values()
        }
        self.headers = Headers()
        self.headers_buffer = Headers()
        self.cookies = SimpleCookie()
        self.cookies_buffer = SimpleCookie()
        self.raw_request = request
        self.raw_request.settimeout(_MAXTIMEOUT)
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
        try:
            requestline = self.raw_requestline.decode()    
        except UnicodeDecodeError as e:
            # Bad request,this is mostly caused by bad SSL support
            self.log_error('Bad request line: %s',e)
            self.close_connection = True
            return False
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
        # Decode the URI
        # Examine the headers and look for a Connection directive.
        try:
            self.headers = Headers.parse(self.rfile)
            if self.headers.get('Cookie'):
                cookies = self.headers.get('Cookie').replace(' ','%20') # esacpe spaces : https://tools.ietf.org/html/rfc6265#section-4.1.1
                self.cookies = SimpleCookie(cookies)                
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
        # Decode the headers,cookies         
        conntype = self.headers.get('Connection')
        if conntype:
            if conntype.lower() == 'close':
                self.close_connection = True
            elif (conntype.lower() == 'keep-alive' and
                self.protocol_version >= "HTTP/1.1"):
                self.close_connection = False
        # Examine the headers and look for an Expect directive
        expect = self.headers.get('Expect')
        if (expect and expect.lower() == "100-continue" and
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
            self.send_header('Connection','keep-alive')
            self.server.handle(request=self)
            return
        except ResponseNotReady as e:
            self.log_error("Bad Response: %s",e)
            self.send_error(HTTPStatus.SERVICE_UNAVAILABLE)
            return
        except socket.timeout as e:
            #a read or a write timed out.  Discard this connection
            # self.log_error("Request timed out: %s", e)
            self.close_connection = True
            return
        except ConnectionAbortedError and ConnectionResetError as e:
            self.close_connection = True
            return            
    def handle(self):
        """Handle multiple requests if necessary."""
        self.log_debug('-- -- Created new HTTP connection')
        self.close_connection = True
        self.handle_one_request()            
        try:
            while not self.close_connection:           
                self.handle_one_request()          
        except Exception as e:
            return self.log_debug('Connection closed %s' % e)
        self.log_debug('Connection closed')
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
        self.log_error("HTTP %d -- %s", code, explain)
        self.clear_header()
        self.send_response_only(code, message)
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
            content = self.format_error_message(
                code   =code,
                message=escape(message, quote=False),
                explain=escape(explain, quote=False),
                request=self
            )
            body = content.encode('UTF-8', 'replace')
            self.send_header("Content-Type", 'text/html;charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
        self.end_headers()

        if self.command != 'HEAD' and body:
            self.wfile.write(body)
    
    def response_line(self,code,message=''):
        return "%s %d %s\r\n" % (self.protocol_version, code, message)

    def send_response(self, code, message=None):
        """Add the response header to the headers buffer and log the
        response code.
        """
        self.log_request(code)
        self.send_header('Content-Length',0)
        self.send_response_only(code, message)

    def send_response_only(self, code, message=None):
        """Send the response header only."""
        if self.request_version != 'HTTP/0.9':
            if message is None:
                if code in self.responses:
                    message = self.responses[code][0]
                else:
                    message = ''
            self.headers_buffer.response_line = self.response_line(code,message)
            # Always send this at the begining
    
    def clear_header(self):
        self.headers_buffer = Headers()

    def send_header(self, keyword, value):
        """Send a MIME header to the headers buffer."""
        if self.request_version != 'HTTP/0.9':
            self.headers_buffer[keyword] = value

        if keyword.lower() == 'connection':
            if value.lower() == 'close':
                self.close_connection = True
            elif value.lower() == 'keep-alive':
                self.close_connection = False

    def send_cookies(self,key,value : Morsel,**kwargs):
        '''Sets a cookie
        - Morsel attributes can be set by:
            
            send_cookies('session','c001code',expires=3600)
        '''    
        self.cookies_buffer[key]=value
        for k in kwargs:self.cookies_buffer[key][k] = kwargs[k]

    def end_headers(self):
        """Adds the cookies and blank line ending of the MIME headers to the buffer,
        then flushes the buffer"""
        if self.request_version != 'HTTP/0.9':         
            if self.cookies_buffer:self.headers_buffer.add_header_line(self.cookies_buffer.output())
            self.flush_headers()

    def flush_headers(self):
        if not self.headers_buffer.response_line:
            raise ResponseNotReady('No response line is present')
        self.wfile.write(self.headers_buffer.encode())
        self.headers_buffer = Headers()

    def log_request(self, code='-'):
        """Log an accepted request.

        This is called by send_response()
        """
        if isinstance(code, HTTPStatus):
            code = code.value
        self.log_debug('"%s" %s',self.requestline, str(code))

    @property    
    def address_string(self):
        """Return the client address."""
        return self.client_address[0] + ':' + str(self.client_address[1])

    @property
    def useragent_string(self):
        """Returns the client UA header,if applicable"""
        return self.headers.get('User-Agent')

    def format_log(self,format,*args):
        """
        Formats a logging message

        Takes `format` and `args` which will construct the base message
        ...and adds other componet into the string

        This method CAN be overwritten.This tries to mimic the
        NGINX Style logging,which looks like this:

            {Client Address} [{Time}] "{Verb} {Path} {HTTP Version}" {Message} {User-Agent}
        """
        if hasattr(self,'path'):            
            return f'{self.address_string} "{self.command} {self.path} {self.base_version_number}" {format % args} {self.useragent_string}'
        else:
            # Fallback
            return f'{self.address_string} {format % args}'
    
    def log_error(self, format, *args):
        """Log an error.

        This is called when a request cannot be fulfilled.  By
        default it passes the message on to log_message().

        Arguments are the same as for log_message().
        """
        self.logger.warning(self.format_log(format,*args))        

    def log_debug(self, format, *args):
        """Log a debug message.

        This is called when a request is done

        Arguments are the same as for log_message().
        """
        self.logger.debug(self.format_log(format,*args))        

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
    
import sched