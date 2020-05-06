'''
# HTTP Protocol

Yes,I know that Websockets are under the hierarchy of HTTP protocol,
But this is just for the ease of use for future protocols to be supplied (like WebDav)

Every thing this server offers are HTTP-Based,while the parent module offers a `Protocol` class,
it's too abstract to be any useful
'''
from . import Protocol,Confidence,RelativeMapping,RelativeModules
import os

class HTTP(Protocol):
    '''
    HTTP Protocol Object

    Offers handy tools for handling HTTP stuff
    '''
    @staticmethod
    def __confidence__(handler) -> float:
        '''Websocket confidence,ranges from 0~1'''
        return super(HTTP,HTTP).__confidence__(handler,{            
            Confidence.const:0.5
        })

    def __init__(self,handler):
        '''Initializes the instance'''
        super().__init__(handler)
    
    def __relative__(self,mapping : RelativeMapping):
        '''
            Handles HTTP relative folder access

            `mapping` : A `RelativeMapping` Object

            Will map every local path to the suggested methods

            The `mapping` **MUST** contain `local` property
        '''
        localpath = mapping.local + '/' + self.handler.path[len(mapping.path):] 
        if os.path.exists(localpath) and os.path.isfile(localpath):
            # A File
            if 'file' in mapping.modules.keys():
                return mapping.modules['file'](self,localpath)
            return 403
        elif os.path.exists(localpath) and not os.path.isfile(localpath):
            # A Folder
            if 'folder' in mapping.modules.keys():
                return mapping.modules['folder'](self,localpath)                
            return 403
        else:
            # Not on the local machine,404 it is
            return 404
        return 200

class Modules(RelativeModules):
    @staticmethod
    def index_folder(proto:HTTP,path,encoding='utf-8',stylesheet=''):
        '''Automaticly indexes the folder to human readable HTML page'''
        proto.handler.send_response(200)
        proto.handler.send_header('Content-Type','text/html; charset=utf-8')
        proto.handler.end_headers()
        html = f'''<head><meta charset="UTF-8"><title>Index of {path}</title>\n'''
        html+= f'''<style>{stylesheet}</style>\n'''
        html+= f'''</head><body><h1>Index of {path}</h1><hr><pre><a href="..">..</a>\n'''
        for item in os.listdir(path):
            html += f'<a href="{proto.handler.path}/{item}"/>{item}</a>\n'
        html+= f'''</pre><hr><body>\n'''
        Modules.write_string(proto,html)

    @staticmethod
    def write_string(proto:HTTP,string,encoding='utf-8'):
        '''Sends a string to the client,DOES NOT flush headers nor send response code'''
        return proto.handler.wfile.write(string.encode(encoding) if type(string) != bytes else string)
    @staticmethod
    def write_file(proto:HTTP,path,chunck=256 * 1024,support_range=True):
        '''Sends a file with path,will flush the headers,and sends a valid HTTP response code'''
        f,s = open(path,'rb'),os.stat(path).st_size
        # Always add this header first
        # For sending all of the file in chunks
        def send_once():                        
            proto.handler.send_response(200)
            proto.handler.send_header('Content-Length',str(s))
            proto.handler.end_headers()            
            chunk = f.read(chunck)
            while chunk:
                try:
                    proto.handler.wfile.write(chunk)
                    chunk = f.read(chunck)
                except Exception:
                    # Connection closed while transmitting,or something else
                    return True
            f.close()
            return True
        # For HTTP 206 : Range headers
        def send_range():
            # Checks range header (if it exists and is satisfiable)
            if not proto.handler.headers.get('Range'):return False
            # If not exist,let `send_once` handle it. Parse range header if exsists
            Range = proto.handler.headers.get('Range')
            if not Range[:6] == 'bytes=' : return False
            # Does not start with `bytes`,let `send_once` do it afterwards
            Range = Range[6:]
            start,end = Range.split('-')
            start,end = int(start if start else 0),int(end if end else s)
            if not (start >= 0 and start < s and end > 0 and end > start and end <= s):
                # Range not satisfiable
                proto.handler.send_response(416)
                proto.handler.end_headers()
                # Stop the routine right here
                return True
            # Otherwise,good to go!
            proto.handler.send_response(206)
            proto.handler.send_header('Accept-Ranges','bytes')
            proto.handler.send_header('Content-Range','bytes %s-%s/%s' % (start,end,s))
            proto.handler.end_headers()            
            try:
                read = 0
                # How much have we already read?
                f.seek(start)
                # Seek from the start
                for bs in range(0,end - start + chunck,chunck):
                    if bs>0:proto.handler.wfile.write(f.read(bs - read))
                    # Read & send the delta amount of data
                    read = bs
            except Exception:
                return True
            return True
        if support_range:
            if send_range():return True
        return send_once()