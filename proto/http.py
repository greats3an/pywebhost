'''
# HTTP Protocol

Yes,I know that Websockets are under the hierarchy of HTTP protocol,
But this is just for the ease of use for future protocols to be supplied (like WebDav)

Every thing this server offers are HTTP-Based,while the parent module offers a `Protocol` class,
it's too abstract to be any useful
'''
from . import Protocol,Confidence
from handler import HTTPRequestHandler
import os

class HTTP(Protocol):
    '''
    HTTP Protocol Object

    Offers handy tools for handling HTTP stuff
    '''
    @staticmethod
    def __confidence__(caller) -> float:
        '''Websocket confidence,ranges from 0~1'''
        return super(HTTP,HTTP).__confidence__(caller,{
            Confidence.headers:{
                'Sec-WebSocket-Key':lambda k:-0.8 if len(k) > 8 else 0,
                # If one has this header,the confidence will be DECREASED because,well,it might be a
                # Websocket request then
            },
            Confidence.const:0.5
            # Always have a confidence of 0.5 for HTTP no matter what
        })

    def __init__(self,caller : HTTPRequestHandler):
        '''Initializes the instance'''
        self.caller = caller
        super().__init__()
    
    def __relative__(self,mapping):
        '''
            Handles HTTP folder access

            `mapping` : A `dict` like iterable,contains the

            `URL` prefix of the path and the actual physical path

            -   For example:

                mapping = {
                    '/','html'
                }
        '''
        targeturl,pathdelta='',65535
        for url in mapping.keys():
            # Does the path begin with the set mapping?
            if self.caller.path[:len(url)] == url:
                # it beigns with such string
                delta = len(self.caller.path) - len(url)
                # How much does it deviate from the requested URL?
                if delta <= pathdelta:
                    # Delta is smaller,choose this instead
                    pathdelta = delta
                    targeturl = url
        if not targeturl:
            '''Not in the mapping list'''
            return 404
        relative_path = mapping[targeturl] + '/' + self.caller.path[len(url):]
        if os.path.exists(relative_path):
            # File exists,starts sending
            self.caller.log_message('Mapping HTTP URL request %s -> %s' % (self.caller.path,relative_path))
            result = self.caller.proto.write_file(relative_path)
            # Do not let server handle HTTP codes
            return
        else:
            # Not on the local machine,404 it is
            self.caller.log_error('Failed Mapping HTTP URL request %s -> %s' % (self.caller.path,relative_path))
            return 404
        return super().__relative__()

    def write_string(self,string,encoding='utf-8'):
        '''Sends a string to the client,DOES NOT flush headers nor send response code'''
        return self.caller.wfile.write(string.encode(encoding) if type(string) != bytes else string)

    def write_file(self,path,chunck=256 * 1024,support_206=True):
        '''Sends a file with path,will flush the headers,and sends a valid HTTP response code'''
        f,s = open(path,'rb'),os.stat(path).st_size
        # Always add this header first
        # For sending all of the file in chunks
        def send_once():                        
            self.caller.send_response(200)
            self.caller.send_header('Content-Length',str(s))
            self.caller.end_headers()            
            chunk = f.read(chunck)
            while chunk:
                try:
                    self.caller.wfile.write(chunk)
                    chunk = f.read(chunck)
                except Exception:
                    # Connection closed while transmitting,or something else
                    return True
            f.close()
            return True
        # For HTTP 206 : Range headers
        def send_range():
            # Checks range header (if it exists and is satisfiable)
            if not self.caller.headers.get('Range'):return False
            # If not exist,let `send_once` handle it. Parse range header if exsists
            Range = self.caller.headers.get('Range')
            if not Range[:6] == 'bytes=' : return False
            # Does not start with `bytes`,let `send_once` do it afterwards
            Range = Range[6:]
            start,end = Range.split('-')
            start,end = int(start if start else 0),int(end if end else s)
            if not (start >= 0 and start < s and end > 0 and end > start and end <= s):
                # Range not satisfiable
                self.caller.send_response(416)
                self.caller.end_headers()
                # Stop the routine right here
                return True
            # Otherwise,good to go!
            self.caller.send_response(206)
            self.caller.send_header('Accept-Ranges','bytes')
            self.caller.send_header('Content-Range','bytes %s-%s/%s' % (start,end,s))
            self.caller.end_headers()            
            try:
                f.seek(start)
                self.caller.wfile.write(f.read(end - start))
            except Exception:
                return True
            return True
        if support_206:
            if send_range():return True
        return send_once()