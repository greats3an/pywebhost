'''
# Websocket Protocol

Offers simple ways of dealing with WS connections
'''
import logging,time,struct,random,base64,hashlib,typing,select
from . import Protocol,Confidence


from enum import IntEnum

class WebsocketOPCODE(IntEnum):
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE_CONN = 0x8
    PING = 0x9
    PONG = 0xA

class Websocket(Protocol):
    '''
        # Websocket object

        - caller          :       RequestHandler object
        - run             :       starts receiving.must be executed during the request
            - Performing `run` will block the current request thread until either the server / client decides to close the connection
        - send            :       put message into queue,then it will be sent later if possible
        - receive         :       immediately recieve a frame
        - callback_receive:       callback for received frame
            - Called once the packet is received
        - kill            :       kills the current session
            - This will set the `keep_alive` flag `False`
        - handshake       :       Performs the handshake,**MUST** be done before any further operation
    '''

    @staticmethod
    def __confidence__(caller) -> float:
        '''Websocket confidence,ranges from 0~1'''
        return super(Websocket,Websocket).__confidence__(caller,{
            Confidence.headers:{
                'Sec-WebSocket-Key':lambda k:0.8 if len(k) > 8 else 0.1,
                # If one request has this header,and the length of it is more than 8,it must
                # Be a websocket request...for the most part
                'Sec-WebSocket-Version':lambda v:0.1,
                'Sec-WebSocket-Extensions':lambda e:0.1
            }
        })

    def __init__(self,caller):  
        '''Creates the websocket object'''  
        self.caller = caller
        self.keep_alive = True
        self.queue = []
        super().__init__()

    def handshake(self):
        # Do Websocket handshake
        self.caller.send_response(101)
        self.caller.send_header('Connection', 'Upgrade')
        self.caller.send_header('Sec-WebSocket-Accept',self.__ws_gen_responsekey(self.caller.headers.get('Sec-WebSocket-Key')))
        self.caller.send_header('Upgrade', 'websocket')
        self.caller.end_headers()
        self.caller.wfile.flush()
        self.caller.log_message('New Websocket session from %s:%s' % self.caller.client_address)   

    def callback_receive(self, frame) -> tuple:
        '''
            Callback funtionality.Executes after `frame` is received

                frame    : The received frame

            Note that a `frame` is a tuple:

                tuple(FIN,RSV1,RSV2,RSV3,OPCODE,MASK,PAYLOAD_LENGTH,MASKEY,PAYLOAD(unmasked))
        '''
        pass


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
                        'Client %s:%s requested to close connection' % self.caller.client_address)
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
            'Websocket Connection closed:%s:%s' % self.caller.client_address)

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
