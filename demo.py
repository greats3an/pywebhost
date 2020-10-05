from io import BytesIO
from codecs import encode
from pywebhost.modules import WriteContentToRequest, writestream
from pywebhost.modules.session import Session, SessionWrapper
from pywebhost import PyWebHost,Request

server = PyWebHost(('',3000))

@server.route('/streaming_test')
def test(initator,request: Request, content):
    WriteContentToRequest(request,
    r'some_random_video.mp4'
    ,True,mime_type='video/mp4')

print('http://localhost:%s' % server.server_address[1])
server.serve_forever()