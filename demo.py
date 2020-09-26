from codecs import encode
from io import BytesIO
from os import read, write
from pywebhost.handler import Request
from re import search
from pywebhost import PyWebHost
from pywebhost.modules import JSONMessageWrapper,ReadContentTo
server = PyWebHost(('',3000))

@server.route('.*')
@JSONMessageWrapper(decode=False,encode=True,read=False,write=True)
def main(request:Request,content):
    request.send_response(200)
    buffer = BytesIO()
    print('read',ReadContentTo(request,buffer))
    return {'good_greif':str(content)}
server.serve_forever()