from http.cookies import Morsel
from random import randrange
from .. import PathMaker
from ..handler import Request
from . import ModuleWrapper, WriteContentToRequest, writestream
import time,random

from hashlib import md5
SESSION_KEY = 'sess_'
SESSION_EXPIRE = 365 * 24 * 3600 # Expires in 1 year by default
_sessions = dict()
class Session(dict):
    
    def mapUri(self,url):
        '''From the request path to local method'''
        if self.paths.hasitem(url):
            return (self.paths[url],True)
        classpath = url.replace('/','_')
        if hasattr(self,classpath):
            return (getattr(self,classpath),False)
        return (None,None)
    @property
    def new_uid(self):
        '''Generates new uid'''
        str_ = '%sDamn%sI%sOughtTorethinkthis' % (SESSION_KEY,time.time() * 1e6,randrange(1e7,1e8-1))
        return md5(str_.encode()).hexdigest()

    def set_session_id(self,**cookie_args):
        session_id = self.new_uid
        self.request.send_cookies(SESSION_KEY,session_id,expires=SESSION_EXPIRE,**cookie_args)            
        return session_id

    @property
    def session_id(self):
        '''The UID of the session

        Returns:
            str : UID
        '''
        if not self.use_session_id:return None
        session_id = self.request.cookies.get(SESSION_KEY) or self.request.cookies_buffer.get(SESSION_KEY)
        if not session_id:
            return None    
        return session_id.value
    
    def get_session(self):
        '''Gets session dictionary by uid,may be overridden
        
        Returns:
            dict : The such dict
        '''
        if self.session_id:
            if not self.session_id in _sessions.keys():_sessions[self.session_id] = {}
            return _sessions[self.session_id]
        return {}

    def set_session(self):
        '''Saves session dictionary by updating it with our values,may be overridden'''
        if self.session_id:
            if not self.session_id in _sessions.keys():_sessions[self.session_id] = {}
            _sessions[self.session_id].update(self)
            return True
        return False

    def onNotFound(self,request : Request=None,content=None):
        '''What to do when the path cannot be mapped'''
        self.request.send_error(404)

    def onCreate(self,request : Request=None,content=None):
        '''What to do when the session starts,e.g. set request mapping'''
        pass

    def onOpen(self,request : Request=None,content=None):
        '''What to do when the session is ready to preform response'''    
        pass

    def onClose(self,request : Request=None,content=None):
        '''What to do when the session ends'''
        pass    

    def __init__(self,request : Request,use_session_id=True) -> None:           
        super().__init__()
        self.request = request    
        self.use_session_id = use_session_id        
        self.update(self.get_session()) # loads session dict
        self.paths = PathMaker()               
        self.onCreate(request,None)
        # try to map the request path to our local path
        request_func,rfunc_from_paths = self.mapUri(self.request.path)
        if not request_func:
            request_func=self.onNotFound

        if rfunc_from_paths and not request_func.__self__ is self:
            self.request_func_result = request_func(self,self.request,None)
        # dict-mapped objects outside current class
        else:self.request_func_result = request_func(self.request,None)            
        # native objects
        self.set_session()            # saves session dict
        self.onClose(request,None)
        # calls the request func                     
        
@ModuleWrapper
def SessionWrapper():
    def suffix(request,function_result):        
        if not issubclass(function_result,Session):
            raise TypeError("Request did not return a Session (or its subclass) object.")
        return function_result(request)
        # Enters the session
    return None,suffix