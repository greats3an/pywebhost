from http.client import SERVICE_UNAVAILABLE
from pywebhost.modules import BadRequestException
import selectors,socketserver,sys

from .handler import Request
from .modules import *
# from .modules import *
from re import fullmatch
from http import HTTPStatus

__version__ = '1.0.5'

class PathMaker(dict):
    '''For storing and handling path mapping
    
        The keys and values are stored as regex pattern strings
        Keys are used to check is the target URL matching the stored URL,which,using regexes will be a great idea

        To set an item:

            pathmaker['/.*'] = lambda a:SendFile('index.html')

        The server will be finding the functions simply with this:

            pathmaker['/']()

    '''
    def __init__(self):
        super().__init__()

    def __setitem__(self, pattern, value):
        '''Sets an path to be routed'''
        if not isinstance(pattern,str):raise Exception('The keys & values must be regexes string')
        super().__setitem__(pattern,value)

    def __getitem__(self, key):
        '''Iterates all keys to find matching one

        The last one added has a better piority of getting called
        '''
        for pattern in list(self.keys())[::-1]: # LIFO
            if fullmatch(pattern,key):
                yield super().__getitem__(pattern)

class PyWebHost(socketserver.ThreadingMixIn, socketserver.TCPServer,):
    '''
        # PyWebHost
        
        To start a server:

            server = PyWebHost(('',1234))
            server.serve_forever()

        You can test by typing `http://localhost:1234` into your browser to retrive a glorious error page ((
    '''
    def handle_error(self, request : Request, client_address):
        """Handle an error gracefully.  May be overridden.

        By default,it prints the latest stack trace
        """
        super().handle_error(request,client_address)


    def serve_forever(self, poll_interval=0.5):
            """Handle one request at a time until shutdown.

            Polls for shutdown every poll_interval seconds. Ignores
            self.timeout. If you need to do periodic tasks, do them in
            another thread.
            """
            self._BaseServer__is_shut_down.clear()
            try:
                # XXX: Consider using another file descriptor or connecting to the
                # socket to wake this up instead of polling. Polling reduces our
                # responsiveness to a shutdown request and wastes cpu at all other
                # times.
                with selectors.SelectSelector() as selector:
                    selector.register(self, selectors.EVENT_READ)
                    while not self._BaseServer__shutdown_request:
                        ready = selector.select(poll_interval)                        
                        # bpo-35017: shutdown() called during select(), exit immediately.
                        if self._BaseServer__shutdown_request:
                            break
                        if ready:
                            self._handle_request_noblock()
                        self.service_actions()
            finally:
                self._BaseServer__is_shut_down.set()

    def __handle__(self, request : Request):
        '''
        Maps the request with the `PathMaker`
        
        The `request` is provided to the router
        '''
        for method in self.paths[request.path]:
            try:
                return method(request,None)
                # Succeed,end this handle call
            except BadRequestException as e:
                # For Other server-side exceptions,let the client know
                return request.send_error(e.code,e.explain)
            except Exception as e:
                return request.send_error(SERVICE_UNAVAILABLE,explain='There was an error processing your request:%s'%e)
        # Request's not handled:No URI matched
        return request.send_error(HTTPStatus.NOT_FOUND)

    def route(self,pattern):
        '''
        Routes a HTTP Request

        e.g:

            @server.route('/')
                def index():lambda a:SendFile('index.html')
        '''
        def wrapper(method):
            self.paths[pattern] = method
            return method
        return wrapper

    def format_error_message(self,code:int,message:str,explain:str,request:Request):
        return f'''
        <head>        
            <title>PyWebHost Error - {self.protocol_version} {code}</title>
        ''' + '''<style>i {position : fixed;bottom:0%;left : 0%;font-size: 14px;}</style>''' + f'''</head><body>
        <div>
            <center><h1>{code} {message}</h1></center>
            <hr><center>{explain}</center><hr>
        </div>
        <i>PyWebHost {__version__}  on {sys.version}</i>
        </body>
        '''

    def __init__(self, server_address : tuple):
        self.paths = PathMaker()
        # A paths dictionary which has `lambda` objects as keys
        self.protocol_version = "HTTP/1.0"
        # What protocol version to use.
        # Here's a note:
        # HTTP 1.1 will automaticly keep the connections alive,so
        # `close_connection = True` needs to be called once the connection is done

        # Error page format. %(`code`)d %(`message`)s %(`explain`)s are usable
        super().__init__(server_address, Request)
