from io import BytesIO
from codecs import encode
from pywebhost.modules import WriteContentToRequest, writestream
from pywebhost.modules.session import Session, SessionWrapper
from pywebhost import PyWebHost,Request

server = PyWebHost(('',3000))
class wsapp(Session):
    def requestTimes(self):
        self['REQUEST_TIMES'] = self['REQUEST_TIMES'] + 1 if 'REQUEST_TIMES' in self.keys() else 1
        return self['REQUEST_TIMES']
    def _(self,request : Request,content):    
        '''The paths are mapped by replacing '/' -> '_',then calling local methods'''
        print('index path access')
        writestream(request,'<p>Hi...<code>%s</code>....For your <code>No.%s</code> access</p>' % (self.session_id,self.requestTimes()))
     
    def onNotFound(self):
        print('not found',self.request.path)
        self.request.send_error(404)
    def onOpen(self):
        self.request.send_response(200)
        print('opened connection for %s' % self.session_id)
    def onClose(self):
        print('exiting connection for %s' % self.session_id)
@server.route('.*')
@SessionWrapper()
def main(self,request:Request,content):
    return wsapp
print('http://localhost:%s' % server.server_address[1])
server.serve_forever()