from codecs import decode
from pywebhost.modules import Base64MessageWrapper
from pywebhost.handler import Request
from pywebhost import PyWebHost,Request,JSONMessageWrapper

import coloredlogs
coloredlogs.install(0)
server = PyWebHost(('',3000))

@server.route('.*')
@Base64MessageWrapper(read=False,write=True,encode=False,decode=False)
def main(request:Request,content):
    print('COOKIE',request.cookies.js_output())
    request.send_response(200)
    request.send_cookies('accepted',True)
    return '<h1>%s</h1>' % request.cookies_buffer

server.serve_forever()