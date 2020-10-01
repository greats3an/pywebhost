from io import BytesIO, StringIO
from build.lib.pywebhost.modules import WriteContentToRequest, writestream
from codecs import decode, encode
from pywebhost.modules.session import Session, SessionWrapper
from pywebhost.modules.websocket import WebsocketSession , WebsocketSessionWrapper
from pywebhost.modules import Base64MessageWrapper
from pywebhost.handler import Request
from pywebhost import PyWebHost,Request,JSONMessageWrapper

import coloredlogs
coloredlogs.install(0)
server = PyWebHost(('',3000))

conns = {}
class wsapp(Session):
    @property
    def request_times(self):
        global conns
        if not self.session_id in conns.keys():
            conns[self.session_id] = 0
        conns[self.session_id] += 1
        return conns[self.session_id]

    def _(self):    
        print('index path access')
        WriteContentToRequest(
            self.request,
            BytesIO(encode('<p>Hi...<code>%s</code>....For your <code>No.%s</code> access</p>' % (self.session_id,self.request_times))),
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