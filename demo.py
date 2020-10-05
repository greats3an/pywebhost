from io import BytesIO
from codecs import encode
from pywebhost.modules import WriteContentToRequest, writestream
from pywebhost.modules.session import Session, SessionWrapper
from pywebhost import PyWebHost,Request

server = PyWebHost(('',3000))

@server.route('/test')
def test(initator,request: Request, content):
    WriteContentToRequest(request,
    r'F:\Shared\html\tf2videos\hevydead.m4v'
    ,True,mime_type='video/mp4')

print('http://localhost:%s' % server.server_address[1])
server.serve_forever()