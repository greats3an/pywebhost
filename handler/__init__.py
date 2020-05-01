import logging,socket
from http import HTTPStatus, server
class HTTPRequestHandler(server.BaseHTTPRequestHandler):
    '''
    Base HTTP request handler Class
    '''

    def __init__(self, request, client_address, server,creator,protos=[]):

        self.logger = logging.getLogger('RequestHandler')
        self.creator = creator
        self.protos = protos
        super().__init__(request, client_address, server)

    def handle_one_request(self):
        """
            Forked from orignal,added websocket method detection
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
            best_confidence = 0
            for proto in self.protos:
                confidence = proto.__confidence__(self)
                if confidence >= best_confidence:
                    best_confidence = confidence
                    self.proto=proto
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