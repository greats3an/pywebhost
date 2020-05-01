import socket
import socketserver
from proto import Protocol,http
from handler import HTTPRequestHandler
import os

class PyWebServer(socketserver.ThreadingMixIn, socketserver.TCPServer,):
    '''
        Base server class
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
            if not type(caller.proto) == http.HTTP:return 500
            # Not http,ignored
            # Now,check the mapping
            targeturl,pathdelta='',65535
            for url in self.relative.keys():
                # Does the path begin with the set mapping?
                if caller.path[:len(url)] == url:
                    # it beigns with such string
                    delta = len(caller.path) - len(url)
                    # How much does it deviate from the requested URL?
                    if delta <= pathdelta:
                        # Delta is smaller,choose this instead
                        pathdelta = delta
                        targeturl = url
            if not targeturl:return 404
            relative_path = self.relative[targeturl] + '/' + caller.path[len(url):]
            caller.log_message('Mapping URL request %s -> %s' % (caller.path,relative_path))
            if os.path.exists(relative_path):
                # File exists,starts sending
                caller.send_response(200)
                caller.end_headers()
                caller.proto.write_file(relative_path)
                return 200
            else:
                # Not on the local machine,404 it is
                return 404


        code = check_for_absolute()

        if code in range(400,500):
            # Abnormal codes,check for relative now
            code = check_for_relative()
        
        if code in range(400,500):
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
            
            @server.path('GET','/',http)
            def root(caller):
                caller.send_response(200)
                caller.end_hedaers()
                caller.wfile.write('Hello World!')
        '''
        def wrapper(func):
            if not command in self.absolute.keys():self.absolute[command] = {}
            if not path in self.absolute[command].keys():self.absolute[command][path] = {}
            self.absolute[command][path][protocol] = func
            return func
        return wrapper

    def __init__(self, server_address,protos):
        # The request mapping
        self.absolute,self.relative = {},{}
        # Absolute path and relative path to the root of the program
        super().__init__(server_address, lambda *args: HTTPRequestHandler(*args, creator=self, protos=protos))