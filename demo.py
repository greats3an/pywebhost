from io import BytesIO
from codecs import encode
from pywebhost.modules import WriteContentToRequest
from pywebhost.modules.session import Session, SessionWrapper
from pywebhost import PyWebHost,Request

server = PyWebHost(('',3000))
class wsapp(Session):
    def requestTimes(self):
        self['REQUEST_TIMES'] = self['REQUEST_TIMES'] + 1 if 'REQUEST_TIMES' in self.keys() else 1
        return self['REQUEST_TIMES']
    def _(self):    
        '''The paths are mapped by replacing '/' -> '_',then calling local methods'''
        print('index path access')
        WriteContentToRequest(
            self.request,
            BytesIO(encode(
                '<p>Hi...<code>%s</code>....For your <code>No.%s</code> access</p>' % (self.session_id,self.requestTimes())
            )),
            mime_type='text/html'
        )    
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
def main(request:Request,content):
    return wsapp
server.serve_forever()