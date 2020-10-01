from random import randrange
from ..handler import Request
from . import ModuleWrapper, WriteContentToRequest, writestream
import time,random

from hashlib import md5
SESSION_KEY = 'sess_'

_sessions = {}
class Session(dict):

    @staticmethod
    def mapUri(url,object_):
        '''From the request path to local method'''
        classpath = url.replace('/','_')
        if hasattr(object_,classpath):
            return getattr(object_,classpath)

    @property
    def new_uid(self):
        '''Generates new uid'''
        str_ = '%sDamn%sI%sOughtTorethinkthis' % (SESSION_KEY,time.time() * 1e6,randrange(1e7,1e8-1))
        return md5(str_.encode()).hexdigest()

    @property
    def session_id(self):
        '''The UID of the session

        Returns:
            str : UID
        '''
        if not self.use_session_id:return None
        session_id = self.request.cookies.get(SESSION_KEY) or self.request.cookies_buffer.get(SESSION_KEY)
        if not session_id:
            session_id = self.new_uid
            self.request.send_cookies(SESSION_KEY,session_id)
            return session_id
        return session_id.value
    
    def get_session(self):
        '''Gets session dictionary by uid,maybe overridden
        
        Returns:
            dict : The such dict
        '''
        if self.session_id:
            if not self.session_id in _sessions.keys():_sessions[self.session_id] = {}
            return _sessions[self.session_id]
        return {}
    def set_session(self):
        '''Saves session dictionary by updating it with our values'''
        if self.session_id:
            if not self.session_id in _sessions.keys():_sessions[self.session_id] = {}
            _sessions[self.session_id].update(self)
            print('SET:',_sessions)

    def onError(self,error):
        '''What to do when an execption occured

        Args:
            error (Execption): The said exception
        '''
        pass

    def onNotFound(self):
        '''What to do when the path cannot be mapped'''
        self.request.send_error(404)

    def onOpen(self):
        '''What to do when the session starts'''
        self.request.send_response(200)

    def onClose(self):
        '''What to do when the session ends'''
        self.request.flush_headers()        

    def __init__(self,request : Request,use_session_id=True) -> None:           
        super().__init__()
        self.request = request    
        self.use_session_id = use_session_id
        # try to map the request path to our local path
        self.request_func = Session.mapUri(self.request.path,self)
        self.update(self.get_session()) # loads session dict
        try:
            if not self.request_func or not '_' in self.request_func.__name__:
                self.onNotFound()
            else:
                self.onOpen()
                self.request_func_result = self.request_func()
                self.onClose()
                self.set_session()            # saves session dict
            # calls the request func                
        except Exception as e:
            self.onError(e)        
        
@ModuleWrapper
def SessionWrapper():
    def suffix(request,function_result):        
        if not issubclass(function_result,Session):
            raise TypeError("Request did not return a Session (or its subclass) object.")
        return function_result(request)
        # Enters the session
    return None,suffix