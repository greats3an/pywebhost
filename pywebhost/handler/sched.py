from datetime import timedelta
import time,typing

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
