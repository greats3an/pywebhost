import socket
import socketserver
from .proto import Protocol,http,RelativeMapping
from .handler import HTTPRequestHandler
import os
import urllib.parse
class PyWebServer(socketserver.ThreadingMixIn, socketserver.TCPServer,):
    '''
        Base server class

        The `__handle__` method handles all HTTP based requests,

        Notes:
        -   Server will check absolute mapping first,then the Direcotry file mapping

        __init__():

                server_address  :   A tuple-like address,for example : `('localhost',1234)`
                proto           :   A iterable of `Protocol`,for example : `[http.HTTP]`
                config          :   Other misc config
    '''

    def __handle__(self, handler : HTTPRequestHandler):
        '''
        Handles the request
        
        handler should have `proto` property for the pre-determined protocol
        '''
        def check_for_absolute():
            if not handler.command in self.absolute.keys():
                # No suitable command
                return 403
            if not handler.path in self.absolute[handler.command].keys():            
                # No suitable path
                return 404
            if not type(handler.proto) in self.absolute[handler.command][handler.path]:
                # No suitable protocol
                return 500
            func = self.absolute[handler.command][handler.path][type(handler.proto)]
            return func(handler)

        def check_for_relative():
            if not handler.command in self.relative.keys():return 403 # No command's matching up
            pathdelta,path = 65534,''            
            for url in self.relative[handler.command].keys():
                # Does the path begin with the set mapping?
                if handler.path[:len(url)] == url:
                    # it beigns with such string
                    delta = len(handler.path) - len(url)
                    # How much does it deviate from the requested URL?
                    if delta <= pathdelta:
                        # Delta is smaller,choose this instead
                        pathdelta = delta
                        path = url
            if not path:return 404 # No such local path mapper could map it? 404
            # Now we have the closest match,lets continue
            if not type(handler.proto) in self.relative[handler.command][path]:return 403 # No protocol is matching up
            mapping = self.relative[handler.command][path][type(handler.proto)]
            # Let the proto do the mapping
            return handler.proto.__relative__(mapping)

        handler.path = urllib.parse.unquote(handler.path)
        # Decode it first,then some
        code = check_for_absolute()

        if code in range(300,600):
            # Abnormal codes,check for relative now
            code = check_for_relative()
        
        if code in range(300,600):
            # Still not normal.Sends the error code
            handler.send_response(code)
            handler.end_headers()

    def add_relative(self,command,path,protocol,modules:dict,**kw):
        '''
        Adds a RELATIVE directory path to the maaping

        For example:

            server.path_relative('GET','/',http.HTTP,{
                'file':http.Modules.write_file,
                'folder':http.Modlues.index_folder
            },local='html')
        '''
        if not command in self.relative.keys():self.relative[command] = {}
        if not path in self.relative[command].keys():self.relative[command][path] = {}
        self.relative[command][path][protocol] = RelativeMapping(path,modules,**kw)

    def path_absolute(self,command,path,protocol):
        '''
        Decorator for ABSOLUTE path and its command
        
        For example:
            
            @server.path_absolute('GET','/',http.HTTP)
            def root(handler):
                handler.send_response(200)
                handler.end_hedaers()
                handler.wfile.write('Hello World!')

        The method **SHOULD** return a HTTP error code afterwards

        if it didn't send by itself,otherwise you *SHOULD NOT DO IT*
        '''
        def wrapper(func):
            if not command in self.absolute.keys():self.absolute[command] = {}
            if not path in self.absolute[command].keys():self.absolute[command][path] = {}
            self.absolute[command][path][protocol] = func
            return func
        return wrapper

    def __init__(self, server_address : tuple,protos : list,**config):
        self.absolute,self.relative = {},{}
        # Absolute path and relative path to the root of the program
        def GetHTTPRequestHandler(*args):
            handler =  HTTPRequestHandler(*args,creator=self, protos=protos,**{'server_version':'PyWebServer'},**config)
            # Always override the `server_version` field
            return handler
        super().__init__(server_address, GetHTTPRequestHandler)