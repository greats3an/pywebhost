from pywebserver import PyWebServer
from pywebserver.modules import HTTPModules,PathMakerModules,HTTPStatus
from pywebserver.handler import RequestHandler
from pywebserver.adapter.websocket import Websocket
import coloredlogs,io
coloredlogs.install(level=0)
# For coloring logs

server = PyWebServer(('localhost',3331))
# Initializes the server without binding it

def GetStyleSheet():return '''
* {
    font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
    font-size: 16px;
}

body {
    margin: 1em;
    background-color: #2d2d2d;
}

a,center {
    color: #666;
    text-decoration: none;
    transition: all 0.1s linear;
}

a:hover {
    color: #ffcc66;
}

h1 {
    color: #CCC;
    font-size: 32px;
}

h3 {
    color: #AAA;
    font-size: 24px;
}

h4 {
    color: #CCC;
    font-size: 18px;
}

pre {
    overflow: auto;
    margin: 1em;
    line-height: 2em;
}'''
# Stylesheet!

@server.route(PathMakerModules.Absolute('/'))
def index(request : RequestHandler):
    HTTPModules.RestrictVerbs(request,['POST'])
    HTTPModules.Redirect(request,'files')

@server.route(PathMakerModules.DirectoryPath('/files/'))
def subfolder(request : RequestHandler):
    HTTPModules.IndexFolder(request,'./' + request.path[7:],GetStyleSheet())
@server.route(PathMakerModules.Absolute('/ws'))
def websocket(request : RequestHandler):
    ws = Websocket(request)
    ws.handshake()
    def callback(msg):
        print(msg)
        ws.send(b'recevied:' + msg[-1])
    ws.callback = callback
    ws.serve()

server.error_message_format = f'<style>{GetStyleSheet()}</style>' + server.error_message_format
# Adds the style sheet to the error page

print('Serving http://localhost:3331 & ws://localhost:3331/ws')
server.serve_forever()