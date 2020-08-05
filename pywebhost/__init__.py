import selectors,socketserver,time,typing
from datetime import timedelta
from .handler import RequestHandler
from .modules import PathMakerModules,UnfinishedException
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

class PyWebHost(socketserver.ThreadingMixIn, socketserver.TCPServer,):
    '''
        # PyWebHost
        
        To start a server:

            server = PyWebHost(('',1234))
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
                        try:
                            self.sched()
                        except Exception:
                            pass
                        # bpo-35017: shutdown() called during select(), exit immediately.
                        if self._BaseServer__shutdown_request:
                            break
                        if ready:
                            self._handle_request_noblock()

                        self.service_actions()
            finally:
                self.__shutdown_request = False
                self.__is_shut_down.set()

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
        super().__init__(server_address, RequestHandler)