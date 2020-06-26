from ..handler import RequestHandler
import time,typing
from datetime import timedelta

def Property(func):
    '''Wrapper for static properties for `Adapter`'''
    @property
    def wrapper(self):
        return getattr(self,'_' + func.__name__)
    @wrapper.setter
    def wrapper(self,value):
        return setattr(self,'_' + func.__name__,value)
    return wrapper

class AdapterConfidence:
    '''
        A pack of confidence mapping types
    '''
    @staticmethod
    def const(request,weights : int):
        '''
            Returns a constant value that DOES NOT change not matter what happens
            
            -   For example:

                weights = {
                    Confidence.const : 1
                }
        '''
        return weights

    @staticmethod
    def headers(request,weights : dict):
        '''
            Confidence that are `headers` weighted,passes header
        
            value to the **lambda** check

            -   For example (Websocket confidence):

                weights = {
                    Confidence.headers : {
                        'Sec-WebSocket-Key':1
                    }
                }            
        '''
        confidence = 0.00
        headers = dict(request.headers)
        for header,value in headers.items():
            if header in weights.keys():
                confidence += weights[header](value)
        return confidence
    @staticmethod
    def commmand(request,weights : dict):
        '''
            Confidence that are `command` weighted,passes command (GET,POST,OPTION,etc)
        
            to a integer

            -   For example (Webdav confidence):

                weights = {
                    Confidence.command : {
                        'COPY' : 1,
                        'CUT'  : 1,
                        'DEL'  : 1
                    } 
                }
                - Note that the command should always be CAPITAL
        '''
        confidence = weights[request.command] if request.command in weights.keys() else 0
        return confidence

    @staticmethod
    def scheme(request,weights : dict):
        '''
            Confidence that are `scheme` weighted,passes scheme
        
            to a integer

            -   For example (Websocket confidence):

                weights = {
                    Confidence.scheme : {
                        'ws' : 1
                    } 
                }
                - Note that the scheme should always be non-capital
        '''
        confidence = weights[request.scheme] if request.scheme in weights.keys() else 0
        return confidence

class Adapter():
    @staticmethod
    def __confidence__(request,weights={}):
        '''
            Base `confidence` method,approximates how well will the apdapter fit
            the request

            `request`   :   A `RequestHandler` Object

            `weights`   :   `Dict` with `Confidence` method as keys,see `Confidence` module for help
        '''
        confidence = 0.00
        for m_confidence in weights.keys():
            confidence += m_confidence(request,weights[m_confidence])
        return confidence

    def __init__(self,request:RequestHandler,ignore_confidence=False):
        '''Initiaztes the adapter with given request
        
           Use `ignore_confidence=True` to bypass `confidence` checking
        '''
        self.request = request
        # Stores the request
        if not ignore_confidence and self.__confidence__(request) < 0.3:
            '''Raise an exception if the confidence is too low'''
            raise Exception("Confidence for '%s' is too low (%s)" % (self.__name__,self.__confidence__(request)))
        return

    def send(self,message):
        '''I/O Output method,needs to be overriden'''
        pass

    def receive(self,message):
        '''I/O Input method,needs to be overriden'''
        pass

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
import os
__all__ = [i[:-3] for i in os.listdir(os.path.dirname(__file__)) if i[-2:] == 'py' and i != '__init__.py']
from . import *