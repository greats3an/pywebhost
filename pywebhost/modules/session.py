from random import randrange
from ..handler import Request
from . import ModuleWrapper, WriteContentToRequest, writestream
import time,random

from hashlib import md5
SESSION_KEY = 'sess_'

def timehash():
    str_ = '%sDamn%sI%sOughtTorethinkthis' % (SESSION_KEY,time.time() * 1e6,randrange(1e7,1e8-1))
    return md5(str_.encode()).hexdigest()

_sessions = {}
class Session(dict):
    '''https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies'''
    @staticmethod
    def mapUri(url,object_):
        '''From the request path to local method'''
        classpath = url.replace('/','_')
        if hasattr(object_,classpath):
            return getattr(object_,classpath)

    @property
    def session_id(self):
        '''The UID of the session

        Returns:
            str : UID
        '''
        session_id = self.request.cookies.get(SESSION_KEY)
        if not session_id:
            session_id = self.uid_func()
            self.request.send_cookies(SESSION_KEY,session_id)
            return session_id
        return session_id.value
    
    def get_session(self):
        '''Gets session dictionary by uid,maybe overridden
        
        Returns:
            dict : The such dict
        '''
        if not self.session_id in _sessions.keys():_sessions[self.session_id] = {}
        return _sessions[self.session_id]

    def set_session(self):
        '''Sets session dictionary by updating it with our values'''
        if not self.session_id in _sessions.keys():_sessions[self.session_id] = {}
        _sessions[self.session_id].update(self)

    def onError(self,error):
        pass

    def onNotFound(self):
        self.request.send_error(404)

    def onOpen(self):
        self.request.send_response(200)

    def onClose(self):
        self.request.flush_headers()
    '''dummy placeholder `on` events'''

    def __init__(self,request : Request,uid_func=timehash) -> None:                
        super().__init__()
        self.request = request
        self.uid_func = uid_func
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
            # calls the request func                
        except Exception as e:
            self.onError(e)
        self.set_session()            # saves session dict
@ModuleWrapper
def SessionWrapper():
    def suffix(request,function_result):        
        if not issubclass(function_result,Session):
            raise TypeError("Request did not return a Session (or its subclass) object.")
        return function_result(request)
        # Enters the session
    return None,suffix