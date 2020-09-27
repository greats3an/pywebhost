'''
# Websocket Protocol

Offers simple ways of dealing with WS connections
'''
import logging
import time
import struct
import random
import base64
import hashlib
import typing
import select
import json
from logging import fatal
from typing import Union
from . import Adapter, AdapterConfidence
from ..handler.sched import BaseScheduler
from http import HTTPStatus
from enum import IntEnum
from datetime import timedelta
from copy import deepcopy

def WebsocketFrameProperty(func):
    '''Wrapper for static properties for `Adapter`'''
    @property
    def wrapper(self):
        return getattr(self,'_' + func.__name__)
    @wrapper.setter
    def wrapper(self,value):
        return setattr(self,'_' + func.__name__,value)
    return wrapper

class WebsocketConnectionClosedException(Exception):
    def __init__(self, is_requested: bool):
        self.is_requested = is_requested
        super().__init__(
            f'Client {"requested" if is_requested else "UNEXPECTLY"} closed connection')


class WebsocketFrame():
    '''Provides docstrings and converters for Websocket Frame bits'''
    @staticmethod
    def bytes(d) -> bytearray:
        '''Converts any datatype to a mutable bytearray'''
        if isinstance(d, str):
            return d.encode()
        if isinstance(d, bytearray) or isinstance(d, bytes):
            return d
        return WebsocketFrame.bytes(json.dumps(d))

    def __init__(self, FIN=1, RSV1=0, RSV2=0, RSV3=0, OPCODE=1, MASK=0, PAYLOAD_LENGTH=0, MASKEY=0, PAYLOAD=b''):
        self._FIN, self._RSV1, self._RSV2, self._RSV3, self._OPCODE, self._MASK, self._PAYLOAD_LENGTH, self._MASKEY, self._PAYLOAD = FIN, RSV1, RSV2, RSV3, OPCODE, MASK, PAYLOAD_LENGTH, MASKEY, self.bytes(
            PAYLOAD)
        if not self._PAYLOAD_LENGTH:
            self._PAYLOAD_LENGTH = len(self._PAYLOAD)
        # Re-applie payload length if not given
        super().__init__()

    @WebsocketFrameProperty
    def FIN(self):
        '''     FIN:  1 bit

      Indicates that this is the final fragment in a message.  The first
      fragment MAY also be the final fragment.'''
        pass

    @WebsocketFrameProperty
    def RSV1(self):
        '''   RSV1, RSV2, RSV3:  1 bit each

      MUST be 0 unless an extension is negotiated that defines meanings
      for non-zero values.  If a nonzero value is received and none of
      the negotiated extensions defines the meaning of such a nonzero
      value, the receiving endpoint MUST _Fail the WebSocket
      Connection_.'''
        pass

    @WebsocketFrameProperty
    def RSV2(self):
        '''   RSV1, RSV2, RSV3:  1 bit each

      MUST be 0 unless an extension is negotiated that defines meanings
      for non-zero values.  If a nonzero value is received and none of
      the negotiated extensions defines the meaning of such a nonzero
      value, the receiving endpoint MUST _Fail the WebSocket
      Connection_.'''
        pass

    @WebsocketFrameProperty
    def RSV3(self):
        '''   RSV1, RSV2, RSV3:  1 bit each

      MUST be 0 unless an extension is negotiated that defines meanings
      for non-zero values.  If a nonzero value is received and none of
      the negotiated extensions defines the meaning of such a nonzero
      value, the receiving endpoint MUST _Fail the WebSocket
      Connection_.'''
        pass

    @WebsocketFrameProperty
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

    @WebsocketFrameProperty
    def MASK(self):
        ''' Mask:  1 bit

      Defines whether the "Payload data" is masked.  If set to 1, a
      masking key is present in masking-key, and this is used to unmask
      the "Payload data" as per Section 5.3.  All frames sent from
      client to server have this bit set to 1.'''
        pass

    @WebsocketFrameProperty
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

    @WebsocketFrameProperty
    def MASKEY(self):
        '''  Masking-key:  0 or 4 bytes

      All frames sent from the client to the server are masked by a
      32-bit value that is contained within the frame.  This field is
      present if the mask bit is set to 1 and is absent if the mask bit
      is set to 0.  See Section 5.3 for further information on client-
      to-server masking.'''
        pass

    @WebsocketFrameProperty
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

        The requests,once being adapted into `Websocket` objects,will be added to the `server`'s 
        `websockets` list as a `Adapter` object
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
        return super(Websocket, Websocket).__confidence__(request, {
            AdapterConfidence.headers: {
                'Sec-WebSocket-Key': lambda v: 1 if v and len(v) > 8 else 0
            }
        })

    def __init__(self, request, ignore_confidence=False, raw_frames=False):
        '''Creates the websocket object

        - `raw_frames`      :       If `true`.the `onRecevie` callback will provide `WebsocketFrames` object instead of `bytearrays`
        (which is the PAYLOAD of the Frame).Note that disabling `raw_frames` will also disable the 
        concatnation of `FIN=0` packets.
        '''
        super().__init__(request, ignore_confidence)
        self.raw_frames = raw_frames
        self.keep_alive, self.did_handshake, self.sched = True, False, BaseScheduler()
        self.__buffer = bytearray()
        # Adds ourself into the server list
        # If the list is not present in the server,create it otherwise
        if not hasattr(self.request.server, 'websockets'):
            setattr(self.request.server, 'websockets', [])
        self.request.server.websockets.append(self)

    def onOpen(self):
        '''Decides what to do once the handshake was perfromed'''
        pass

    def handshake(self):
        '''Do Websocket handshake,must be done first after the request is parsed'''
        self.request.send_response(HTTPStatus.SWITCHING_PROTOCOLS)
        self.request.send_header('Connection', 'Upgrade')
        self.request.send_header('Sec-WebSocket-Accept', self.__ws_gen_responsekey(
            self.request.headers.get('Sec-WebSocket-Key')))
        self.request.send_header('Upgrade', 'websocket')
        self.request.end_headers()
        self.did_handshake = True
        self.request.log_request(
            'New Websocket session from %s:%s' % self.request.client_address)
        self.onOpen()

    def onReceive(self, frame: Union[bytearray,WebsocketFrame]):
        '''Decides what to do once a frame has been recevied'''
        pass

    def _onReceive(self, frame: WebsocketFrame):
        '''Base recevie method,deals with interal websocket codes and such
        DO NOT OVERRIDE unless you know what you're doing
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
        # All checks passed,proceed to perfrom the callback
        if self.raw_frames:
            return self.onReceive(frame)
        # Return raw frames (including websockets masks) if said so
        # Otherwise,parse the frame and return a bytearray as result
        if not frame.FIN:
            # A Single websocket frame can contain data up to 2^63 Bytes (8192 PB,the MSB's 0)
            # But some clients use FIN bitmask to send little packets over time
            # ...for safety measures.Which means more work needed to be done
            return self.__buffer.extend(frame.PAYLOAD)
            # Extend the buffer
        elif frame.FIN:
            # We have received,the buffer may be cleared next time
            self.__buffer.extend(frame.PAYLOAD)
            self.onReceive(self.__buffer)
            # Perform the real callback
            return self.__buffer.clear()
            # Clear the buffer,Done

    def send(self, frame: WebsocketFrame):
        '''
            Appends message to the buffer,Every message will be constructed as a Websocket Frame
        '''
        return self.request.wfile.write(self.__websocket_constructframe(frame))

    def receive(self) -> WebsocketFrame:
        '''
            Receives a single frame,will block thread
        '''
        return self.__websocket_recieveframe(self.request.rfile)

    def serve(self, ping_interval=1):
        '''
            Starts processing I/O,and blocks until connection is closed or flag is set


            `ping_interval`   :   WS `Ping` heartbeat interval in seconds,set `0` to disable it
        '''
        if not self.did_handshake:
            raise Exception("Handshake was not performed!")
        # Setup periodic tasks
        @self.sched.new(delta=timedelta(seconds=ping_interval))
        def ping(): self.send(WebsocketFrame(OPCODE=Websocket.PING))
        # PING the client websocket every given seconds
        while self.keep_alive:
            try:
                readable = select.select(
                    [self.request.request], [], [], 1.0)[0]
                if readable:
                    frame = self.receive()
                    self._onReceive(frame)
                self.sched()
                # Checks & runs periodic tasks
                time.sleep(0.01)
            except Exception as e:
                # Quit once any exception occured
                self.request.log_error(str(e))
                self.keep_alive = False
        self._onClose()

    def close(self):
        '''Tries to close the connection via sending CLOSE_CONN Opcode'''
        self.send(WebsocketFrame(OPCODE=Websocket.CLOSE_CONN))

    def close_forced(self):
        '''Forcily closes the connection by killing the `serve` thread'''
        self.keep_alive = False

    def _onClose(self):
        '''Decides what to do once the connection is closed,either by the server or the client'''
        self.request.log_debug('Websocket Connection closed')
        self.request.server.websockets.remove(self)
        # kicks ourself out
        self.onClose()

    def onClose(self):
        pass

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
        if not isinstance(data, WebsocketFrame):
            data = WebsocketFrame(PAYLOAD=data)
        binary.append(self.__construct_byte(
            [data.FIN, data.RSV1, data.RSV2, data.RSV3] + self.__extract_byte(data.OPCODE)[4:]))
        # 1st byte:FIN,RSV1,RSV2,RSV3,OPCODE
        if data.PAYLOAD_LENGTH >= 126 and data.PAYLOAD_LENGTH < 65536:
            binary.append(self.__construct_byte(
                [data.MASK] + self.__extract_byte(126)[1:]))
            '''
            If 126, the following 2 bytes interpreted as a 16-bit unsigned integer are the payload length.
            '''
            binary.extend(struct.pack('>H', data.PAYLOAD_LENGTH))
        elif data.PAYLOAD_LENGTH >= 65536 and data.PAYLOAD_LENGTH < 2**63:  # mfw the MSB is always 0
            binary.append(self.__construct_byte(
                [data.MASK] + self.__extract_byte(127)[1:]))
            '''
            If 127, the following 8 bytes interpreted as a 64-bit unsigned integer
            '''
            binary.extend(struct.pack('>Q', data.PAYLOAD_LENGTH))
        elif data.PAYLOAD_LENGTH >= 0 and data.PAYLOAD_LENGTH < 126:
            '''
            Otherwise,the following 7 bytes (after MASK) are interpeted as a 7 bit integer
            '''
            binary.append(self.__construct_byte(
                [data.MASK] + self.__extract_byte(data.PAYLOAD_LENGTH)[1:]))
        else:
            raise Exception("Bad payload length!")
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
