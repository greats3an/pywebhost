import socket
import socketserver
from proto import Protocol,http
from handler import HTTPRequestHandler
import os

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

    def __handle__(self, caller : HTTPRequestHandler):
        '''
        Handles the request
        
        Caller should have `proto` property for the pre-determined protocol
        '''
        def check_for_absolute():
            if not caller.path in self.absolute[caller.command].keys():            
                # No absolute path found
                return 404
            if not type(caller.proto) in self.absolute[caller.command][caller.path]:
                # No suitable protocol
                return 500
            func = self.absolute[caller.command][caller.path][type(caller.proto)]
            return func(caller)

        def check_for_relative():
            return caller.proto.__relative__(self.relative)

        code = check_for_absolute()

        if code in range(300,600):
            # Abnormal codes,check for relative now
            code = check_for_relative()
        
        if code in range(300,600):
            # Still not normal.Sends the error code
            caller.send_response(code)
            caller.end_headers()

    def directory(self,urlpath,physical):
        '''
        Appends a Direcotry path mapping

        For example:

            server.directory('/','html')
        '''
        self.relative[urlpath] = physical

    def path(self,command,path,protocol):
        '''
        Decorator for path and its command
        
        For example:
            
            @server.path('GET','/',http.HTTP)
            def root(caller):
                caller.send_response(200)
                caller.end_hedaers()
                caller.wfile.write('Hello World!')

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