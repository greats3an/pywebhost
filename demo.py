from pywebserver import PyWebServer
from pywebserver.modules import HTTPModules,PathMakerModules,HTTPStatus
from pywebserver.handler import RequestHandler
from pywebserver.adapter.websocket import Websocket,WebsocketFrame
import coloredlogs,io
coloredlogs.install(level=0)
# For coloring logs

server = PyWebServer(('',3310))
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

a,center,span {
    color: #CCC;
    text-decoration: none;
    transition: all 0.1s linear;
}

p {
    color: #999;
}

a:hover,span:hover {
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

@server.route(PathMakerModules.Absolute('/files'))
def index(request : RequestHandler):
    HTTPModules.RestrictVerbs(request,['GET'])
    # Redirects to '/files'
    HTTPModules.Redirect(request,'files/')

@server.route(PathMakerModules.DirectoryPath('/files/'))
def subfolder(request : RequestHandler):
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
    ws.send_nowait('<b>Name yourself:</b>')
    def others():return ",".join([ws_.name if hasattr(ws_,"name") else "[PENDING]" for ws_ in ws_list if ws_ != ws])
    def callback(msg:WebsocketFrame):   
        if msg.OPCODE == Websocket.PONG:return
        if not hasattr(ws,'name'):
            # 1st message,aquire username
            setattr(ws,'name', msg.PAYLOAD.decode())
            ws.send(f'<b>Welcome,{ws.name}</b>...<i>Other online users:{others()}</i>')
            return
        for ws_ in ws_list:
            if ws != ws_:ws_.send(f'{ws.name} says: {msg[-1].decode()}')
            # Avoid sending to ourselfS
        ws.send('<i>[your message has been sent to %s other members (%s)]</i>' % (len(ws_list) - 1,others()))
    ws.callback = callback
    ws.serve()
    ws_list.remove(ws)
    # Removes session after it closes


@server.route(PathMakerModules.Absolute('/'))
def index(request : RequestHandler):
    # Indexes folders of local path and renders a webpage
    ws_html = io.BytesIO((f'<style>{GetStyleSheet()}</style>' + open('demo_ws.html',encoding='utf-8').read()).encode(encoding='utf-8'))
    request.send_header('Content-Type','text/html; charset=utf-8')
    HTTPModules.WriteFileHTTP(request,ws_html)

server.error_message_format = f'<style>{GetStyleSheet()}</style>' + server.error_message_format
# Adds the style sheet to the error page

print('Serving...http://localhost:3310')
server.serve_forever()