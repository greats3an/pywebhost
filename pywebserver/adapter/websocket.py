'''
# Websocket Protocol

Offers simple ways of dealing with WS connections
'''
import logging,time,struct,random,base64,hashlib,typing,select,json
from . import Adapter,AdapterConfidence
from http import HTTPStatus
from enum import IntEnum



class WebsocketConnectionClosedException(Exception):
    def __init__(self,is_requested : bool):
        self.is_requested = is_requested
        super().__init__(f'Client {"requested" if is_requested else "UNEXPECTLY"} closed connection')

def WSProperty(func):
    '''Wrapper for `WebsocketFrame`'''
    @property
    def wrapper(self):
        return getattr(self,'_' + func.__name__)
    @wrapper.setter
    def wrapper(self,value):
        return setattr(self,'_' + func.__name__,value)
    return wrapper  

class WebsocketFrame():
    '''Provides docstrings and converters for Websocket Frame bits'''
    encoding = 'utf-8'
    @staticmethod
    def bytes(d) -> bytearray:
        '''Converts any datatype to a mutable bytearray'''
        if isinstance(d,str):return d.encode(encoding=WebsocketFrame.encoding)
        if isinstance(d,bytearray) or isinstance(d,bytes): return d
        return WebsocketFrame.bytes(json.dumps(d))

    def __init__(self,FIN=1,RSV1=0,RSV2=0,RSV3=0,OPCODE=1,MASK=0,PAYLOAD_LENGTH=0,MASKEY=0,PAYLOAD=b''):
        self._FIN,self._RSV1,self._RSV2,self._RSV3,self._OPCODE,self._MASK,self._PAYLOAD_LENGTH,self._MASKEY,self._PAYLOAD = FIN,RSV1,RSV2,RSV3,OPCODE,MASK,PAYLOAD_LENGTH,MASKEY,self.bytes(PAYLOAD)
        super().__init__()
    @WSProperty
    def FIN(self):
        '''     FIN:  1 bit

      Indicates that this is the final fragment in a message.  The first
      fragment MAY also be the final fragment.'''
        pass
    @WSProperty
    def RSV1(self):
        '''   RSV1, RSV2, RSV3:  1 bit each

      MUST be 0 unless an extension is negotiated that defines meanings
      for non-zero values.  If a nonzero value is received and none of
      the negotiated extensions defines the meaning of such a nonzero
      value, the receiving endpoint MUST _Fail the WebSocket
      Connection_.'''
        pass
    @WSProperty
    def RSV2(self):
        '''   RSV1, RSV2, RSV3:  1 bit each

      MUST be 0 unless an extension is negotiated that defines meanings
      for non-zero values.  If a nonzero value is received and none of
      the negotiated extensions defines the meaning of such a nonzero
      value, the receiving endpoint MUST _Fail the WebSocket
      Connection_.'''
        pass
    @WSProperty
    def RSV3(self):
        '''   RSV1, RSV2, RSV3:  1 bit each

      MUST be 0 unless an extension is negotiated that defines meanings
      for non-zero values.  If a nonzero value is received and none of
      the negotiated extensions defines the meaning of such a nonzero
      value, the receiving endpoint MUST _Fail the WebSocket
      Connection_.'''
        pass
    @WSProperty
    def OPCODE(self):
        '''Opcode:  4 bits

      Defines the interpretation of the "Payload data".  If an unknown
      opcode is received, the receiving endpoint MUST _Fail the
      WebSocket Connection_.  The following values are defined.You can use those stored
      in `Websocket` class as well

      -  %x0 denotes a continuation frame

      -  %x1 denotes a text frame

      -  %x2 denotes a binary frame

      -  %x3-7 are reserved for further non-control frames

      -  %x8 denotes a connection close

      -  %x9 denotes a ping

      -  %xA denotes a pong

      -  %xB-F are reserved for further control frames'''
        pass
    @WSProperty
    def MASK(self):
        ''' Mask:  1 bit

      Defines whether the "Payload data" is masked.  If set to 1, a
      masking key is present in masking-key, and this is used to unmask
      the "Payload data" as per Section 5.3.  All frames sent from
      client to server have this bit set to 1.'''
        pass
    @WSProperty
    def PAYLOAD_LENGTH(self):
        '''   Payload length:  7 bits, 7+16 bits, or 7+64 bits

      The length of the "Payload data", in bytes: if 0-125, that is the
      payload length.  If 126, the following 2 bytes interpreted as a
      16-bit unsigned integer are the payload length.  If 127, the
      following 8 bytes interpreted as a 64-bit unsigned integer (the
      most significant bit MUST be 0) are the payload length.  Multibyte
      length quantities are expressed in network byte order.  Note that
      in all cases, the minimal number of bytes MUST be used to encode
      the length, for example, the length of a 124-byte-long string
      can't be encoded as the sequence 126, 0, 124.  The payload length
      is the length of the "Extension data" + the length of the
      "Application data".  The length of the "Extension data" may be
      zero, in which case the payload length is the length of the
      "Application data".'''
        pass
    @WSProperty
    def MASKEY(self):
        '''  Masking-key:  0 or 4 bytes

      All frames sent from the client to the server are masked by a
      32-bit value that is contained within the frame.  This field is
      present if the mask bit is set to 1 and is absent if the mask bit
      is set to 0.  See Section 5.3 for further information on client-
      to-server masking.'''
        pass
    @WSProperty
    def PAYLOAD(self):
        ''' Payload data:  (x+y) bytes

      The "Payload data" is defined as "Extension data" concatenated
      with "Application data".'''
        pass
    
    
class Websocket(Adapter):
    '''
        # Websocket Adapter

        - request          :      BaseHandler request
        - handshake        :       Performs the handshake,--MUST-- be done before any further operation
        - serve            :       Starts serving the client and blocks the thread
            - Performing `run` will block the current request thread until either the server / client decides to close the connection
        - send            :       put message into queue,then it will be sent later if possible
        - receive         :       immediately recieve a frame
        - callback        :       callback for received frame
            - Called once the packet is received
        - shutdown
            - This will set the kill switch

        eg:

            class WebsocketApp(Websocket):
                def callback(self,frame : WebsocketFrame):
                    print('Message:',frame.PAYLOAD)
            @server.rotue(PathMakerModlues.Absoulte('/'))
            def websocket(request):
                ws = WebsocketApp(request)
                ws.handshake()
                ws.serve()
            ...
    '''
    # Websocket OpCodes
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE_CONN = 0x8
    PING = 0x9
    PONG = 0xA
    @staticmethod
    def __confidence__(request) -> float:
        '''Websocket confidence,ranges from 0~1'''
        return super(Websocket,Websocket).__confidence__(request,{
            AdapterConfidence.headers:{
                'Sec-WebSocket-Key':lambda v:1 if v and len(v) > 8 else 0
            }
        })

    def __init__(self,request,*a,**k):  
        '''Creates the websocket object
        
           Use `ignore_confidence=True` to bypass `confidence` checking
        ''' 
        super().__init__(request,*a,**k) 
        self.keep_alive,self.did_handshake = True,False
        # Adds ourself into the server list
        if not hasattr(self.request.server,'websockets'):setattr(self.request.server,'websockets',[])
        self.request.server.websockets.append(self)
        

    def handshake(self):
        '''Do Websocket handshake,must be done first after the request is parsed'''
        self.request.send_response(HTTPStatus.SWITCHING_PROTOCOLS)
        self.request.send_header('Connection', 'Upgrade')
        self.request.send_header('Sec-WebSocket-Accept',self.__ws_gen_responsekey(self.request.headers.get('Sec-WebSocket-Key')))
        self.request.send_header('Upgrade', 'websocket')
        self.request.end_headers()
        self.did_handshake = True
        self.request.log_request('New Websocket session from %s:%s' % self.request.client_address)   

    def callback(self, frame:WebsocketFrame):
        '''
            Callback funtionality.By default,it responses to PINGs,and CLOSE-connection requests

            And returns False if this frame should not be processed anymore (e.g. recevied `PING` `PONG` `CLOSE_CONN`,etc),vise-versa

            `super()` this function *FIRST*

            e.g

                if super().callback(frame):
                    ...
        '''
        if frame.OPCODE == Websocket.PING:
            # ping -> pong -> end
            self.send(WebsocketFrame(OPCODE=Websocket.PONG))
            return False
        if frame.OPCODE == Websocket.PONG:
            # pong -> ignore -> end
            return False
        elif frame.OPCODE == Websocket.CLOSE_CONN:
            # client requested to close connection -> end
            self.send(WebsocketFrame(OPCODE=Websocket.CLOSE_CONN))
            # accepts such request,raises an exception
            raise WebsocketConnectionClosedException(True)
        return True

    def send(self,frame:WebsocketFrame):
        '''
            Appends message to the buffer,Every message will be constructed as a Websocket Frame
        '''
        return self.request.wfile.write(self.__websocket_constructframe(frame))

    def receive(self) -> WebsocketFrame:
        '''
            Receives a single frame,will block thread
        '''
        return self.__websocket_recieveframe(self.request.rfile)

    def serve(self,ping_interval=1):
        '''
            Starts processing I/O,and blocks until connection is closed or flag is set

                
            `ping_interval`   :   WS `Ping` heartbeat interval,set `0` to disable it
        '''
        if not self.did_handshake:
            raise Exception("Websocket did not perform handshake!")
        tick_ping = 0
        while self.keep_alive:
            try:
                readable = select.select([self.request.request],[],[],1.0)[0]     
                if readable:
                    frame = self.receive()
                    self.callback(frame)
                if ping_interval and time.time() - tick_ping >= ping_interval:
                    self.send(WebsocketFrame(OPCODE=Websocket.PING))
                    tick_ping = time.time()
                time.sleep(0.01)
            except Exception as e:
                # Quit once any exception occured
                self.request.log_error(str(e))
                self.keep_alive = False
        self.request.log_debug('Websocket Connection closed')
        self.request.server.websockets.remove(self)
        # kicks ourself out

    def close(self):
        '''Tries to close the connection via sending CLOSE_CONN Opcode'''
        self.send(WebsocketFrame(OPCODE=Websocket.CLOSE_CONN))

    def close_forced(self):
        '''Forcily closes the connection by killing the `serve` thread'''
        self.keep_alive = False

    def __websocket_constructframe(self, data: WebsocketFrame) -> bytearray:
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
        binary = bytearray()
        if not isinstance(data,WebsocketFrame):data=WebsocketFrame(PAYLOAD=data)
        binary.append(self.__construct_byte([data.FIN, data.RSV1,data.RSV2,data.RSV3] + self.__extract_byte(data.OPCODE)[4:]))
        # 1st byte:FIN,RSV1,RSV2,RSV3,OPCODE
        PAYLOAD_LENGTH = len(data.PAYLOAD) if not data.PAYLOAD_LENGTH else data.PAYLOAD_LENGTH
        if PAYLOAD_LENGTH >= 126 and PAYLOAD_LENGTH < 65536:
            binary.append(self.__construct_byte(
                [data.MASK] + self.__extract_byte(126)[1:]))
            '''
            If 126, the following 2 bytes interpreted as a 16-bit unsigned integer are the payload length.
            '''
            binary.extend(struct.pack('>H', PAYLOAD_LENGTH))
        elif PAYLOAD_LENGTH >= 65536 and PAYLOAD_LENGTH < 2--64:
            binary.append(self.__construct_byte(
                [data.MASK] + self.__extract_byte(127)[1:]))
            '''
            If 127, the following 8 bytes interpreted as a 64-bit unsigned integer
            '''
            binary.extend(struct.pack('>Q', PAYLOAD_LENGTH))
        else:
            binary.append(self.__construct_byte(
                [data.MASK] + self.__extract_byte(PAYLOAD_LENGTH)[1:]))
        if data.MASK:
            # Reserved:A server must not mask any frames that it sends to the client
            mkey = self.__gen_maskey()
            data.PAYLOAD = self.__mask(data.PAYLOAD, mkey)
            binary.extend(mkey)
        # 2nd+ bytes: PAYLOAD_LENGTH,MASK,MASKEY
        binary.extend(data.PAYLOAD)
        return binary

    def __websocket_recieveframe(self, rfile: typing.BinaryIO) -> WebsocketFrame:
        '''
        Receiving frame,PAYLOAD is unmasked

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
        return WebsocketFrame(FIN, RSV1, RSV2, RSV3, OPCODE, MASK, PAYLOAD_LENGTH, MASKEY, PAYLOAD)

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
