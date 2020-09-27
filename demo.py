from codecs import decode
from pywebhost.modules import Base64MessageWrapper
from pywebhost.handler import Request
from pywebhost import PyWebHost,Request,JSONMessageWrapper

import coloredlogs
coloredlogs.install(0)
server = PyWebHost(('',3000))

@server.route('.*')
@Base64MessageWrapper(read=True,write=False,encode=False,decode=True)
@JSONMessageWrapper(decode=False,read=False)
def main(request:Request,content):
    return {'result':content}

server.serve_forever()