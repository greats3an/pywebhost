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
# Multiple items of the same path will be tested if previous handler raised `UnfinishedException`
@server.route(PathMakerModules.Absolute('/'))
def index(request : RequestHandler):
    HTTPModules.RestrictVerbs(request,['POST'])
    # This is to show how you map certain HTTP Verbs to the same path
    # Visiting with a web browser will cause UnfinishedException
    # As it uses verb `GET` for getting webpages.
    # Thus,the next `index()` is called since they share the same path

@server.route(PathMakerModules.Absolute('/'))
def index(request : RequestHandler):
    HTTPModules.RestrictVerbs(request,['GET'])
    # Redirects to 'files'
    HTTPModules.Redirect(request,'files')

@server.route(PathMakerModules.Absolute('/files'))
def files(request : RequestHandler):
    HTTPModules.RestrictVerbs(request,['GET'])
    # Redirects to 'files/'
    HTTPModules.Redirect(request,'files/')

@server.route(PathMakerModules.DirectoryPath('/files/'))
def files(request : RequestHandler):
    # Indexes folders of local path and renders a webpage
    HTTPModules.IndexFolder(request,'./' + request.path[7:],GetStyleSheet())

ws_list = []
@server.route(PathMakerModules.Absolute('/ws'))
def websocket(request : RequestHandler):
    # A simple WebSocket echo server,which will boardcast
    # Message to all connected sessions
    ws = Websocket(request)
    ws_list.append(ws)
    # Store the session
    ws.handshake()
    ws.send_nowait(b'<b>Name yourself:</b>')
    def callback(msg):   
        if not hasattr(ws,'name'):
            # 1st message,aquire username
            setattr(ws,'name', msg[-1].decode())
            ws.send(f'<b>Welcome,{ws.name}</b>...<i>Online users:{",".join([ws_.name if hasattr(ws_,"name") else "[PENDING]" for ws_ in ws_list])}</i>'.encode())                       
            return
        for ws_ in ws_list:
            if ws != ws_:ws_.send(
                f'{ws.name} says: {msg[-1].decode()}'.encode()
            )
            # Avoid sending to ourself
        ws.send(('<i>[your message has been sent to %s other members]</i>' % (len(ws_list) - 1)).encode())
    ws.callback = callback
    ws.serve()
    ws_list.remove(ws)
    # Removes session after it closes

server.error_message_format = f'<style>{GetStyleSheet()}</style>' + server.error_message_format
# Adds the style sheet to the error page

print('Serving http://localhost:3331 & ws://localhost:3331/ws')
server.serve_forever()