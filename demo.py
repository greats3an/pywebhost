from io import BytesIO
from codecs import encode
from os import path
from pywebhost.modules import BinaryMessageWrapper, WriteContentToRequest, writestream
from pywebhost.modules.session import Session, SessionWrapper
from pywebhost import PyWebHost,Request

server = PyWebHost(('',3000))
TEMPLATE = '''<h1> List of routed paths</h1> %s '''
@server.route('/streaming_test')
def test(initator,request: Request, content):
    WriteContentToRequest(request,
    'some_random_video.mp4'
    ,True,mime_type='video/mp4')
class SessionTest(Session):    
    def onCreate(self):
        @BinaryMessageWrapper(read=False)
        def _session_test_(initiator,request: Request, content):
            request.send_response(200)        
            return self.session_id        
        self.paths['.*session_test.*'] = _session_test_        
@server.route('/session_test')
@SessionWrapper()
def sess(initator,request: Request, content):
    return SessionTest
@server.route('/')
@BinaryMessageWrapper(read=False)
def index(initator,request: Request, content):
    request.send_response(200)
    paths = ['<a href=%s>%s</a></br>' % (path,path) for path in server.paths]
    return TEMPLATE % ''.join(paths)
print('http://localhost:%s' % server.server_address[1])
server.serve_forever()