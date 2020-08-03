from pywebserver import PyWebServer
from pywebserver.modules import HTTPModules,PathMakerModules,HTTPStatus
from pywebserver.handler import RequestHandler
from pywebserver.adapter import Adapter
from pywebserver.adapter.websocket import Websocket,WebsocketFrame
import coloredlogs,io,random
coloredlogs.install(level=0)
# For coloring logs
port = 3300
server = PyWebServer(('',port))
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

    i {
        color:#CCC;
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
    }
'''
# Stylesheet!

# Server routing: Whatever comes later has higher piority of getting tested

@server.route(PathMakerModules.DirectoryPath('/files/'))
def subfolder(request : RequestHandler):
    # Indexes folders of local path and renders a webpage
    HTTPModules.IndexFolder(request,'./' + request.path[7:],GetStyleSheet())

@server.route(PathMakerModules.Absolute('/files'))
def index(request : RequestHandler):
    HTTPModules.RestrictVerbs(request,['GET'])
    # Redirects to '/files'
    HTTPModules.Redirect(request,'files/')

boardcasts = [{'sender':'server','msg':'<i>Server started at %s</i>' % RequestHandler.time_string(None)}]
class WSChat(Websocket):
    # Using classes to do websocket jobs is recommended
    # This demo showcases a server-client based chat system
    # Which each client runs on its own thread
    def msg(self,obj):return {'sender':self.name,'msg':str(obj)} if not isinstance(obj,dict) else obj

    def boardcast(self,message):
        global boardcasts
        msg = self.msg(message)
        boardcasts.append(msg)
        for ws in server.websockets:ws.send(msg)

    def onReceive(self, frame : WebsocketFrame):
        global boardcasts
        def others():return ",".join([ws_.name if hasattr(ws_,"name") else "[PENDING]" for ws_ in server.websockets if ws_ != self])
        if not hasattr(self,'name'):
            # 1st message,aquire username
            setattr(self,'name', frame.PAYLOAD.decode())

            self.boardcast({'sender':'server','msg':f'<i>{self.name} Logged in</i>'})
            self.boardcast({'sender':'server','msg':f'<i>Other online users:{others() if others() else "No others online"}</i>'})

            return
        message = frame.PAYLOAD.decode()
        self.boardcast(message)

@server.route(PathMakerModules.Absolute('/ws'))
def websocket(request : RequestHandler):
    global boardcasts
    # A simple WebSocket echo server,which will boardcast
    # Message to all connected sessions
    ws = WSChat(request)
    # Store the session
    ws.handshake()
    for b in boardcasts:ws.send(b)
    ws.send({'sender':'server','msg':'<b>Name yourself by typing your name here:</b>'})
    ws.serve()
    # Starts serving and blocks the current thread

@server.route(PathMakerModules.Absolute('/'))
def index(request : RequestHandler):
    # Indexes folders of local path and renders a webpage
    ws_html = io.BytesIO((f'<style>{GetStyleSheet()}</style>' + open('demo_ws.html',encoding='utf-8').read()).encode(encoding='utf-8'))
    request.send_header('Content-Type','text/html; charset=utf-8')
    HTTPModules.WriteStream(request,ws_html)

@server.route(PathMakerModules.Absolute('/ze-backdoor'))
def clear(request : RequestHandler):
    if not 'pass' in request.query.keys() or request.query['pass'][0] != ''.join([chr(ord(i) ^ 0x01) for i in 'cnofhnson']):
        return request.send_error(HTTPStatus.LOCKED,'Wrong passcode!' if 'pass' in request.query.keys() else 'Missing `pass` query string','Have you read the code yet?')
    global boardcasts
    boardcasts = [{'sender':'server','msg':'SOMEONE Activated the backdoor!'}]
    for ws in server.websockets:ws.send({'sender':'rce','msg':'reload'})
    request.send_error(200,'Success','The backdoor has been acivated')

@server.route(PathMakerModules.Absolute('/urls'))
def urls(request:RequestHandler):
    # Prints out all urls defined in the server
    html = [PathMakerModules.GetModuleProperty(i)['target'] for i in server.paths.keys()]
    request = Adapter(request)
    request.send(f'<style>{GetStyleSheet()}</style>' + '</br>\n'.join([f'<a href="{i}">{i}</a>' for i in html]))
server.error_message_format = f'<style>{GetStyleSheet()}</style>' + server.error_message_format
# Adds the style sheet to the error page

print(f'Serving...http://localhost:{port}')
server.serve_forever()
