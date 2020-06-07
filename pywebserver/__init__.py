import socket,socketserver,os,urllib.parse
from .handler import RequestHandler
from .modules import PathMakerModules,UnfinishedException
from http import HTTPStatus

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
        try:
            return super().__setitem__(keytester, super().__getitem__(keytester) + [value])
        except KeyError:
            super().__setitem__(keytester, [value])
        # Initalizes with an empty list

    def __getitem__(self, key):
        '''Iterates all keys to find matching one

        Which,whatever comes up in the list first,has a higher chace of getting sele
        '''
        for keytester in self.keys():
            if keytester(key):
                return super().__getitem__(keytester)
        return None

class PyWebServer(socketserver.ThreadingMixIn, socketserver.TCPServer,):
    '''
        Base server class

        The `__handle__` method handles all HTTP based requests,

        Notes:
        -   Server will check absolute mapping first,then the Direcotry file mapping

        __init__():

                server_address  :   A tuple-like address,for example : `('localhost',1234)`                

        To start a server:

            server = PyWebServer(('',1234))
            server.serve_forever()

        This way,you can test by typing `http://localhost:1234` into your browser
        
        And BEHOLD!An error page.

        Surely you are going to read the documents to make sth with this.
    '''
    def handle_error(self, request : RequestHandler, client_address):
        """Handle an error gracefully.  May be overridden.

        By default,it does nothing
        """
        pass
    
    def __handle__(self, request : RequestHandler):
        '''
        Maps the request with the `PathMaker`
        
        The `request` is provided to the router
        '''
        methods = self.paths[request.path]
        if not methods:
            return request.send_error(HTTPStatus.NOT_FOUND)
        for method in methods:
            try:
                return method(request)
                # Succeed,end this handle call
            except UnfinishedException as e:
                # Ignore UnfinishedException and go on
                pass
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