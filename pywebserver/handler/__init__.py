import logging,socket
from http import HTTPStatus, server
from urllib.parse import urlparse,parse_qs
class HTTPRequestHandler(server.BaseHTTPRequestHandler):
    '''
    Base HTTP request handler Class
    '''

    def __init__(self, request, client_address, server,creator,protos=[],**config):

        self.logger = logging.getLogger('RequestHandler')
        self.creator = creator
        self.protos = protos
        self.scheme, self.netloc, self.path, self.params, self.query, self.fragment = ('' for _ in range(0,6))
        for key,value in config.items():setattr(self,key,value)
        super().__init__(request, client_address, server)

    def handle_one_request(self):
        """
            Handles the request
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
            self.scheme, self.netloc, self.path, self.params, self.query, self.fragment = urlparse(self.path)
            self.query = parse_qs(self.query) # Decodes query string to a `dict`
            # Decode the URL
            best_confidence = 0
            for proto in self.protos:
                confidence = proto.__confidence__(self)
                if confidence >= best_confidence:
                    best_confidence = confidence
                    self.proto=proto
            # Find best-matching protocol
            self.proto=self.proto(self)
            # Initialize the protocol
            self.creator.__handle__(self)
            # Lets the server handle it
            self.wfile.flush()
        except socket.timeout as e:
            # a read or a write timed out.  Discard this connection
            self.log_error("Request timed out: %r", e)
            self.close_connection = True
            return

    def send_response(self, code, message=None):
        """Add the response header to the headers buffer and log the
        response code.

        Also send two standard headers with the server software
        version and the current date.

        """
        self.log_request(code)
        self.send_response_only(code, message)
        self.send_header('Server', '%s %s' % (self.server_version,self.sys_version))
        self.send_header('Date', self.date_time_string())

    def log_request(self, code='-', size='-'):
        """Log an accepted request.

        This is called by send_response().

        """
        if isinstance(code, HTTPStatus):
            code = code.value
        self.log_message('"%s" %s %s %s',self.requestline,self.path,str(code), str(size))

    def log_message(self, format, *args):
        """Log an arbitrary message.

        This is used by all other logging functions.  Override
        it if you have specific logging wishes.

        The first argument, FORMAT, is a format string for the
        message to be logged.  If the format string contains
        any % escapes requiring parameters, they should be
        specified as subsequent arguments (it's just like
        printf!).

        The client ip and current date/time are prefixed to
        every message.

        Modified to use `logging` module instead of `stderr`
        """
        self.logger.debug("%s %s" % (self.address_string(), format % args))

    def log_error(self, format, *args):
        """Log an error.

        This is called when a request cannot be fulfilled.  By
        default it passes the message on to log_message().

        Arguments are the same as for log_message().

        XXX This should go to the separate error log.

        """

        self.logger.error("%s %s" % (self.address_string(), format % args))
import os
__all__ = [i[:-3] for i in os.listdir(os.path.dirname(__file__)) if i[-2:] == 'py' and i != '__init__.py']
from . import *