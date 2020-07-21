import socket,socketserver,os,urllib.parse
from .handler import RequestHandler
from .modules import PathMakerModules,UnfinishedException
from http import HTTPStatus

def Property(func):
    '''Wrapper for static properties for `PyWebServer`'''
    @property
    def wrapper(self):
        return getattr(self,'_' + func.__name__)
    @wrapper.setter
    def wrapper(self,value):
        return setattr(self,'_' + func.__name__,value)
    return wrapper

class PathMaker(dict):
    '''For storing and handling path mapping
    
        The keys and values are stored as functions.Or their addresses to be exact
        Keys are used to check is the target URL matching the stored URL,which,using regexes will be a great idea

        To set an item:

            pathmaker[Absoulte('/')] = lambda a:SendFile('index.html')

        Thus,the server will be finding the functions simply with this:

            pathmaker['/']()

        Easy,right?
    '''
    def __init__(self):
        super().__init__()

    def __setitem__(self, keytester, value):
        '''
        Setting an item,multiple values can be stacked '''
        if not callable(keytester) or not callable(value):raise Exception('The keys & values must be callable')
        super().__setitem__(keytester,value)

        # Initalizes with an empty list

    def __getitem__(self, key):
        '''Iterates all keys to find matching one

        Which,whatever comes up in the list first,has a higher chace of getting sele
        '''
        for keytester in list(self.keys())[::-1]: # the last added path has the highest piority
            if keytester(key):
                yield super().__getitem__(keytester)

class PyWebServer(socketserver.ThreadingMixIn, socketserver.TCPServer,):
    '''
        # PyWebServer
        
        To start a server:

            server = PyWebServer(('',1234))
            server.serve_forever()

        This way,you can test by typing `http://localhost:1234` into your browser
        And BEHOLD!An error page.

        Surely you are going to read the documents to make sth with this.
    '''
    def handle_error(self, request : RequestHandler, client_address):
        """Handle an error gracefully.  May be overridden.

        By default,it prints the latest stack trace
        """
        super().handle_error(request,client_address)

    
    def __handle__(self, request : RequestHandler):
        '''
        Maps the request with the `PathMaker`
        
        The `request` is provided to the router
        '''
        excepted_excptions = 0
        for method in self.paths[request.path]:
            try:
                return method(request)
                # Succeed,end this handle call
            except UnfinishedException:
                # Ignore UnfinishedException and go on
                excepted_excptions += 1
            except Exception as e:
                # For Other server-side exceptions,let the client know
                return request.send_error(HTTPStatus.SERVICE_UNAVAILABLE,explain=str(e))
        # Request's not handled,and no UnfinishedException is ever called:No URI matched
        if not excepted_excptions:return request.send_error(HTTPStatus.NOT_FOUND)
        # No fatal exceptions,assume the response is unfinished
        request.send_error(HTTPStatus.FORBIDDEN)
        request.end_headers()
        # Give out HTTP 403 error

    def route(self,keytester : PathMakerModules):
        '''
        Routes a HTTP Request

        e.g:

            @server.route(Absoulte('/'))
                def index():lambda a:SendFile('index.html')
        '''
        def wrapper(method):
            self.paths[keytester] = method
            return method
        return wrapper

    def __init__(self, server_address : tuple):
        self.paths = PathMaker()
        # A paths dictionary which has `lambda` objects as keys
        self.protocol_version = "HTTP/1.0"
        # What protocol version to use.
        # Here's a note:
        # HTTP 1.1 will automaticly keep the connections alive,so
        # `close_connection = True` needs to be called once the connection is done
        self.error_message_format = """\
<head>
    <meta http-equiv="Content-Type" content="text/html;charset=utf-8">
    <title>PyWebserver Error - %(code)d</title>
</head>
<body>
    <center><h1>%(code)d %(message)s</h1></center>
    <hr><center>%(explain)s - PyWebserver</center>
</body>
"""
        # Error page format. %(`code`)d %(`message`)s %(`explain`)s are usable
        super().__init__(server_address, RequestHandler)