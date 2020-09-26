import selectors,socketserver,time,typing
from datetime import timedelta
from .handler import Request
# from .modules import *
from re import fullmatch
from http import HTTPStatus

def Property(func):
    '''Wrapper for static properties for `PyWebHost`'''
    @property
    def wrapper(self):
        return getattr(self,'_' + func.__name__)
    @wrapper.setter
    def wrapper(self,value):
        return setattr(self,'_' + func.__name__,value)
    return wrapper

class BaseScheduler():
    '''
    Base Synchronus time/tick - based schduler

    The tasks are ran in whatever thread has called the `tick` function,which means it's thread-safe
    and blocking.

    The delta can be either a `timedelta` object,or a `int`

    `timedelta` is straight-forward:Only execute this function when the time has reached the delta value
    `int` is for executing per `loop`,which is when the `tick` function is called

    e.g.

            sched = BaseScheduler()
            @sched.new(delta=1,run_once=True)
            def run():
                print('Hello,I was ran the first!')
            @sched.new(delta=2,run_once=True)
            def run():
                print('Bonjour,I was ran the second!')
            @sched.new(delta=timedelta(seconds=5),run_once=True)
            def run():
                print('I was executed,and will never be executed again')
            @sched.new(delta=timedelta(seconds=1),run_once=False)
            def run():
                print('...one second has passed!')
            @sched.new(delta=timedelta(seconds=8),run_once=False)
            def run():
                print('...eight second has passed!')        
            while True:
                time.sleep(1)
                sched()
    '''
    def __init__(self):
        # The ever increasing tick of the operations perfromed (`tick()` called)
        self.ticks = 0
        # The list of jobs to do
        self.jobs = []

    def __time__(self):
        return time.time()

    def new(self,delta : typing.Union[timedelta,int],run_once=False):
        def wrapper(func):
            # Once wrapper is called,the function will be added to the `jobs` list
            self.jobs.append([delta,func,self.__time__(),self.ticks,run_once])
            # The 3rd,4th argument will be updated once the function is called
            return func
        return wrapper

    def __call__(self):return self.tick()

    def tick(self):        
        self.ticks += 1
        for job in self.jobs:
            # Iterate over every job
            delta,func,last_time,last_tick,run_once = job
            execution = False
            if isinstance(delta,timedelta):
                if self.__time__() - last_time >= delta.total_seconds():
                    execution = True
            elif isinstance(delta,int):
                if self.ticks - last_tick >= delta:
                    execution = True         
            # Sets the execution flag is the tickdelta is at its set valve       
            else:
                raise Exception("Unsupported detla function is provided!")
            if execution:
                # Update the execution timestamps
                job[2:4] = self.__time__(),self.ticks
                # Execute the job,synchronously
                func()
                if run_once:
                    # If only run this function once
                    self.jobs.remove(job) # Deletes it afterwards

class PathMaker(dict):
    '''For storing and handling path mapping
    
        The keys and values are stored as regex pattern strings
        Keys are used to check is the target URL matching the stored URL,which,using regexes will be a great idea

        To set an item:

            pathmaker[re.compile('/')] = lambda a:SendFile('index.html')

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
                        self.sched()
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
                return method(request)
                # Succeed,end this handle call
            except Exception as e:
                # For Other server-side exceptions,let the client know
                return request.send_error(HTTPStatus.SERVICE_UNAVAILABLE,explain=str(e))
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

    def __init__(self, server_address : tuple):
        self.paths = PathMaker()
        # A paths dictionary which has `lambda` objects as keys
        self.sched = BaseScheduler()
        # A synconous schedulation class which runs in the listening thread
        self.protocol_version = "HTTP/1.0"
        # What protocol version to use.
        # Here's a note:
        # HTTP 1.1 will automaticly keep the connections alive,so
        # `close_connection = True` needs to be called once the connection is done
        self.error_message_format = """\
<head>
    <meta http-equiv="Content-Type" content="text/html;charset=utf-8">
    <title>PyWebHost Error - %(code)d</title>
</head>
<body>
    <center><h1>%(code)d %(message)s</h1></center>
    <hr><center>%(explain)s - PyWebHost</center>
</body>
"""
        # Error page format. %(`code`)d %(`message`)s %(`explain`)s are usable
        super().__init__(server_address, Request)