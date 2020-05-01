'''
# HTTP Protocol

Yes,I know that Websockets are under the hierarchy of HTTP protocol,
But this is just for the ease of use for future protocols to be supplied (like WebDav)

Every thing this server offers are HTTP-Based,while the parent module offers a `Protocol` class,
it's too abstract to be any useful
'''
from . import Protocol,Confidence
from handler import HTTPRequestHandler
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
    
    def write_string(self,string,encoding):
        '''Sends a string to the client'''
        return self.caller.wfile.write(string.encode(encoding))

    def write_file(self,path,chunck=256 * 1024,support_206=True):
        '''Sends a file with path'''
        def send_once():
            f = open(path,'rb')
            chunk = f.read(chunck)
            while chunk:
                try:
                    self.caller.wfile.write(chunk)
                    chunk = f.read(chunck)
                except Exception:
                    return False
            f.close()
            return True
        def send_range():
            # Checks range header (if it exists and is satisfiable)
            if not self.caller.headers.get('Range'):return False
            # TODO:Actually perfrom the partial sending thing...
            return False
        if support_206:
            if send_range():return True
        return send_once()