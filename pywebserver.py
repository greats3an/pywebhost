'''
# PyWebServer

    A Simple HTTP/WebSocket Server 
'''

import base64
import hashlib
import random
import select
import socket
import socketserver
import struct
import sys
import time
import typing
import ssl

from http import HTTPStatus, server
from enum import IntEnum

import logging
import coloredlogs
coloredlogs.install(level=logging.DEBUG)


class WebsocketOPCODE(IntEnum):
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE_CONN = 0x8
    PING = 0x9
    PONG = 0xA


class RequestHandler(server.BaseHTTPRequestHandler):
    '''
    HTTP / WS handler.Modified to access parent methods
    '''

    def __init__(self, request, client_address, server, parent=None):
        self.parent = parent
        self.logger = logging.getLogger('RequestHandler')
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
            mname = self.command
            if self.headers.get('Upgrade') == 'websocket':
                # Websocket job,processing these headers.
                # If processed,it means the request is valid
                self.ws_ver = self.headers.get('Sec-WebSocket-Version')
                self.ws_key = self.headers.get('Sec-WebSocket-Key')
                self.ws_ext = self.headers.get('Sec-WebSocket-Extensions')
                mname = 'WS'
            self.parent.do_METHOD(mname,self)
            # Execute method defined in parent
            # actually send the response if not already done.
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


class WebsocketSession():
    '''
        WebsocketSession object

            caller          :       RequestHandler object with properties ``

            run             :       starts receiving.must be executed during the request
            send            :       put message into queue,then it will be sent later if possible
            receive         :       immediately recieve a frame
            callback_receive:       callback for received frame
            kill            :       kills the current session
            message__received:      callback function.called once packet is received
    '''

    def callback_receive(self, frame) -> tuple:
        '''
            Callback funtionality.Executes after `frame` is received

                frame    : The received frame

            Note that a `frame` is a tuple:

                tuple(FIN,RSV1,RSV2,RSV3,OPCODE,MASK,PAYLOAD_LENGTH,MASKEY,PAYLOAD(unmasked))
        '''
        pass

    def __init__(self, caller: RequestHandler):
        # A request is a socket object,from socketserver
        self.caller = caller
        self.queue = []
        self.client_address = caller.client_address
        self.keep_alive = True
        # Do handshake
        self.__websocket_handshake()
        self.caller.log_message(
            'New Websocket session from %s:%s' % self.caller.client_address)   
        super().__init__()

    def handle_once(self):
        '''Handles IO event for once'''
        # Using select() to process selectable IOs
        inputs = (sel:=([self.caller.request], [self.caller.request], [], 1.0))[0]
        outputs = sel[1]
        if inputs:
            # target socket is ready to send,process frame,then callback
            if (frame:= self.receive()):
                if frame[4] == WebsocketOPCODE.CLOSE_CONN:
                    # client requested to close connection
                    self.send_nowait(
                        b'', OPCODE=WebsocketOPCODE.CLOSE_CONN)
                    raise Exception(
                        'Client %s:%s requested to close connection' % self.client_address)
                self.callback_receive(frame)
        if outputs:
            # target socket is ready to receive,sending frame from the top of the list
            if self.queue:
                self.caller.wfile.write(self.queue.pop(0))

    def run(self):
        '''
            Starts processing I/O,and blocks until connection is closed or flag is set
        '''
        while self.keep_alive:
            try:
                self.handle_once()
                time.sleep(0.01)
            except Exception as e:
                # Quit once any exception occured
                self.caller.log_message(str(e))
                self.keep_alive = False
        self.caller.log_request(
            'Websocket Connection closed:%s:%s' % self.client_address)

    def send_nowait(self, PAYLOAD, FIN=1, OPCODE=WebsocketOPCODE.TEXT, MASK=0):
        '''
            Sends a constructed message without putting it inside the queue
        '''
        self.caller.wfile.write(
            self.__websocket_constructframe(PAYLOAD, FIN, OPCODE, MASK))
        self.caller.wfile.flush()

    def send(self, PAYLOAD, FIN=1, OPCODE=WebsocketOPCODE.TEXT, MASK=0):
        '''
            Adds a constructed message to the queue,OPCODE included
        '''
        self.queue.append(self.__websocket_constructframe(
            PAYLOAD, FIN, OPCODE, MASK))

    def receive(self):
        '''
            Receives a single frame
        '''
        try:
            return self.__websocket_recieveframe(self.caller.rfile)
        except Exception:
            return None

    def kill(self):
        '''
            Set keep_alive flag False
        '''
        self.keep_alive = False

    def wait(self):
        '''
            Wait until messages are all sent
        '''
        while self.queue:
            pass

    def __websocket_handshake(self):
        # Do Websocket handshake
        self.caller.send_response(101)
        self.caller.send_header('Connection', 'Upgrade')
        self.caller.send_header('Sec-WebSocket-Accept',
                                self.__ws_gen_responsekey(self.caller.ws_key))
        self.caller.send_header('Sec-WebSocket-Version', self.caller.ws_ver)
        self.caller.send_header('Upgrade', 'websocket')
        self.caller.end_headers()
        self.caller.wfile.flush()

    def __websocket_constructframe(self, data: bytearray, FIN=1, OPCODE=WebsocketOPCODE.TEXT, MASK=0):
        '''
        Constructing frame
        5.2.  Base Framing Protocol:https://tools.ietf.org/html/rfc6455#section-5.2
            0                   1                   2                   3
            0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
            +-+-+-+-+-------+-+-------------+-------------------------------+
            |F|R|R|R| opcode|M| Payload len |    Extended payload length    |
            |I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
            |N|V|V|V|       |S|             |   (if payload len==126/127)   |
            | |1|2|3|       |K|             |                               |
            +-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
            |     Extended payload length continued, if payload len == 127  |
            + - - - - - - - - - - - - - - - +-------------------------------+
            |                               |Masking-key, if MASK set to 1  |
            +-------------------------------+-------------------------------+
            | Masking-key (continued)       |          Payload Data         |
            +-------------------------------- - - - - - - - - - - - - - - - +
            :                     Payload Data continued ...                :
            + - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
            |                     Payload Data continued ...                |
            +---------------------------------------------------------------+
        '''
        (header:= bytearray()).append(self.__construct_byte([FIN, 0, 0, 0] + self.__extract_byte(OPCODE)[4:]))
        # 1st byte:FIN,RSV1,RSV2,RSV3,OPCODE
        PAYLOAD_LENGTH = len(data)
        if PAYLOAD_LENGTH >= 126 and PAYLOAD_LENGTH < 65536:
            header.append(self.__construct_byte(
                [MASK] + self.__extract_byte(126)[1:]))
            '''
            If 126, the following 2 bytes interpreted as a 16-bit unsigned integer are the payload length.
            '''
            header.extend(struct.pack('>H', PAYLOAD_LENGTH))
        elif PAYLOAD_LENGTH >= 65536 and PAYLOAD_LENGTH < 2**64:
            header.append(self.__construct_byte(
                [MASK] + self.__extract_byte(127)[1:]))
            '''
            If 127, the following 8 bytes interpreted as a 64-bit unsigned integer
            '''
            header.extend(struct.pack('>Q', PAYLOAD_LENGTH))
        else:
            header.append(self.__construct_byte(
                [MASK] + self.__extract_byte(PAYLOAD_LENGTH)[1:]))
        if MASK:
            # Reserved:A server must not mask any frames that it sends to the client
            mkey = self.__gen_maskey()
            data = self.__mask(data, mkey)
            header.extend(mkey)
        header.extend(data)
        return header

    def __websocket_recieveframe(self, rfile: typing.BinaryIO = None):
        '''
        Receiving frame，note that PAYLOAD is returned unmasked
        5.2.  Base Framing Protocol:https://tools.ietf.org/html/rfc6455#section-5.2
            0                   1                   2                   3
            0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
            +-+-+-+-+-------+-+-------------+-------------------------------+
            |F|R|R|R| opcode|M| Payload len |    Extended payload length    |
            |I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
            |N|V|V|V|       |S|             |   (if payload len==126/127)   |
            | |1|2|3|       |K|             |                               |
            +-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
            |     Extended payload length continued, if payload len == 127  |
            + - - - - - - - - - - - - - - - +-------------------------------+
            |                               |Masking-key, if MASK set to 1  |
            +-------------------------------+-------------------------------+
            | Masking-key (continued)       |          Payload Data         |
            +-------------------------------- - - - - - - - - - - - - - - - +
            :                     Payload Data continued ...                :
            + - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
            |                     Payload Data continued ...                |
            +---------------------------------------------------------------+
        '''
        if not rfile:
            rfile = self.caller.rfile
        b1, b2 = rfile.read(2)
        FIN, RSV1, RSV2, RSV3 = self.__extract_byte(b1)[:4]
        OPCODE = self.__construct_byte(self.__extract_byte(b1)[4:])
        MASK = self.__get_bit_at(b1, 0)
        PAYLOAD_LENGTH = self.__construct_byte(
            [0] + self.__extract_byte(b2)[1:])
        if PAYLOAD_LENGTH == 126:
            '''
            If 126, the following 2 bytes interpreted as a 16-bit unsigned integer are the payload length.
            '''
            PAYLOAD_LENGTH = struct.unpack('>H', rfile.read(2))[0]
        elif PAYLOAD_LENGTH == 127:
            '''
            If 127, the following 8 bytes interpreted as a 64-bit unsigned integer
            '''
            PAYLOAD_LENGTH = struct.unpack('>Q', rfile.read(8))[0]
        MASKEY = rfile.read(4)
        PAYLOAD = rfile.read(PAYLOAD_LENGTH)
        PAYLOAD = self.__mask(PAYLOAD, MASKEY)
        return (FIN, RSV1, RSV2, RSV3, OPCODE, MASK, PAYLOAD_LENGTH, MASKEY, PAYLOAD)

    def __gen_maskey(self):
        '''
            Generate a 32-bit random key
        '''
        return bytearray([random.randint(0, 255) for i in range(0, 4)])

    def __mask(self, d, k):
        '''
        5.3.  Client-to-Server Masking:https://tools.ietf.org/html/rfc6455#section-5.3
        Octet i of the transformed data ("transformed-octet-i") is the XOR of
        octet i of the original data ("original-octet-i") with octet at index
        i modulo 4 of the masking key ("masking-key-octet-j")
                j                           =                          i MOD 4
                transformed-octet-i = original-octet-i XOR masking-key-octet-j
            To get DECODED, loop through the octets (bytes a.k.a. characters for text data) of ENCODED and XOR the octet with the (i modulo 4)th octet of MASK.
        '''
        return bytearray([d[i] ^ k[i % 4] for i in range(0, len(d))])

    def __construct_byte(self, a):
        '''
            Form an array of 1s and 0s,gets a byte (little-endian)
        '''
        return int(''.join([str(i) for i in a]), 2)

    def __extract_byte(self, a):
        '''
            Turns a byte into an array of 1s and 0s            
        '''
        return [self.__get_bit_at(a, i) for i in range(0, 8)]

    def __get_bit_at(self, a, i):
        '''
            Get bit at certain poistion,stars from the highest bit indexed 0
        '''
        return ((a << i) & 128) >> 7

    def __ws_gen_responsekey(self, key):
        '''
        As described in RFC6455:https://tools.ietf.org/html/rfc6455#section-1.3
            Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==

            For this header field, the server has to take the value (as present
            in the header field, e.g., the base64-encoded [RFC4648] version minus
            any leading and trailing whitespace) and concatenate this with the
            Globally Unique Identifier (GUID, [RFC4122]) "258EAFA5-E914-47DA-
            95CA-C5AB0DC85B11" in string form, which is unlikely to be used by
            network endpoints that do not understand the WebSocket Protocol.  A
            SHA-1 hash (160 bits) [FIPS.180-3], base64-encoded (see Section 4 of
            [RFC4648]), of this concatenation is then returned in the server's
            handshake.
        '''
        GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        rkey = key + GUID    # contact in string form
        # returns SHA-1 hash and b64 encoded concatenation
        rkey = base64.b64encode(hashlib.sha1(rkey.encode()).digest())
        return rkey.decode()


class WebServer(socketserver.ThreadingMixIn, socketserver.TCPServer,):
    '''
        Server capable of handing both HTTP and WebSocket requests 

            ws__sessions        :       All alive WebSocket sessions
            do__###             :       HTTP Functions
            new_wsession        :       Callback once a new session is created
    '''

    def accept_websocket(self, caller: RequestHandler) -> WebsocketSession:
        '''
            Accepts a websocket session

                caller    :       A RequestHandler object
        '''
        return WebsocketSession(caller)

    def do_METHOD(self, method,caller: RequestHandler):
        if not method in self.METHODS.keys():
            raise Exception("Not supported method %s" % method)
        if not caller.path in self.METHODS[method].keys():            
            caller.send_response(404)
            caller.end_headers()
            return
        self.METHODS[method][caller.path](caller)

    def path(self,method,path):
        '''
        Decorator for path and its methods
        
        For example:
            
            @server.path('GET','/')
            def root(caller):
                caller.send_response(200)
                caller.end_hedaers()
                caller.wfile.write('Hello World!')
        '''
        def wrapper(func):
            if not method in self.METHODS.keys():self.METHODS[method] = {}
            self.METHODS[method][path] = func
            return func
        return wrapper

    def __init__(self, server_address):
        # HTTP Methods to be processed
        self.METHODS = {}
        super().__init__(server_address, lambda *args: RequestHandler(*args, parent=self))


class SecureWebServer(WebServer):
    '''SSL-Wrapped WebServer

        cert            :       Path to cert file
        key             :       Path to key file
        ssl_version     :       SSL Version
        cert_reqs       :       Certification requirements
    '''

    def server_activate(self):
        """Added SSL socket wrapping"""
        self.socket = ssl.wrap_socket(
            self.socket,
            certfile=self.certfile,
            keyfile=self.keyfile,
            ssl_version=self.ssl_version,
            cert_reqs=self.cert_reqs,
            server_side=True
        )
        self.socket.listen(self.request_queue_size)

    def __init__(self, server_address, cert, key, ssl_version=ssl.PROTOCOL_TLSv1, cert_reqs=ssl.CERT_NONE):
        self.certfile = cert
        self.keyfile = key
        self.ssl_version = ssl_version
        self.cert_reqs = cert_reqs
        super().__init__(server_address)


if __name__ == "__main__":
    server = WebServer(('localhost', 3331))
    @server.path('GET','/')
    def GET(caller: RequestHandler):
        caller.send_response(200)
        caller.send_header('Content-Type', 'text/html;encoding=utf-8')
        caller.end_headers()
        caller.wfile.write(f'''
            <h1>Welcome to PyWebServer!</h1>
            <h3>For Websocket ECHO Server:</h3>
            <a href="ws://{server.server_address[0]}:{server.server_address[1]}">
            ws://{server.server_address[0]}:{server.server_address[1]}
            </a>
        '''.encode())
        caller.wfile.flush()
    
    @server.path('WS','/')
    def WS(caller: RequestHandler):
        # Accepts the reqeust
        session = server.accept_websocket(caller)

        def callback_receive(frame):
            logging.info('New message from %s:%s:%s' %
                         (*session.client_address, frame[-1].decode()))
            session.send(b'OK.' + frame[-1])
        session.callback_receive = callback_receive
        session.run()

    logging.info('''
    Echo-server serving:
        ws://{0}:{1}
        http://{0}:{1}'''.format(*server.server_address))
    server.serve_forever()
