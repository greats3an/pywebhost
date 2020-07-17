from pywebserver import PyWebServer
from pywebserver.modules import HTTPModules,PathMakerModules,HTTPStatus
from pywebserver.handler import RequestHandler
from pywebserver.adapter import Adapter
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

@server.route(PathMakerModules.Absolute('/files'))
def index(request : RequestHandler):
    HTTPModules.RestrictVerbs(request,['GET'])
    # Redirects to '/files'
    HTTPModules.Redirect(request,'files/')

@server.route(PathMakerModules.DirectoryPath('/files/'))
def subfolder(request : RequestHandler):
    # Indexes folders of local path and renders a webpage
    HTTPModules.IndexFolder(request,'./' + request.path[7:],GetStyleSheet())

messages = '<i>Server started at %s</i>' % RequestHandler.time_string(None)
class WSChat(Websocket):
    # Using classes to do websocket jobs is recommended
    def boardcast(self,message):
        global messages
        messages += f'<p>{message}<p>'
        for ws in server.websockets:
            if self != ws:ws.send(message)

    def onReceive(self, frame):
        global messages
        def others():return ",".join([ws_.name if hasattr(ws_,"name") else "[PENDING]" for ws_ in server.websockets if ws_ != self])
        if not hasattr(self,'name'):
            # 1st message,aquire username
            setattr(self,'name', frame.PAYLOAD.decode())
            self.boardcast(f'<i>{self.name} Logged in</i>')
            self.send(f'<b>Welcome,{self.name}</b>...<i>Other online users:{others()}</i>')
            self.send('<b>Message Histroy</b><hr>')
            self.send(messages)
            self.send('<hr>')
            return
        message = f'{self.name} says: {frame.PAYLOAD.decode()}'
        self.boardcast(message)
        self.send('<i>[your message has been sent to %s other members (%s)]</i>' % (len(server.websockets) - 1,others()))

@server.route(PathMakerModules.Absolute('/ws'))
def websocket(request : RequestHandler):
    # A simple WebSocket echo server,which will boardcast
    # Message to all connected sessions
    ws = WSChat(request)
    # Store the session
    ws.handshake()
    ws.send('<b>Name yourself:</b>')
    ws.serve()
    # Starts serving until exceptions

@server.route(PathMakerModules.Absolute('/'))
def index(request : RequestHandler):
    # Indexes folders of local path and renders a webpage
    ws_html = io.BytesIO((f'<style>{GetStyleSheet()}</style>' + open('demo_ws.html',encoding='utf-8').read()).encode(encoding='utf-8'))
    request.send_header('Content-Type','text/html; charset=utf-8')
    HTTPModules.WriteFileHTTP(request,ws_html)

@server.route(PathMakerModules.Absolute('/urls'))
def urls(request:RequestHandler):
    # Prints out all urls defined in the server
    html = [PathMakerModules.GetModuleProperty(i)['target'] for i in server.paths.keys()]
    request = Adapter(request)
    request.send(f'<style>{GetStyleSheet()}</style>' + '</br>\n'.join([f'<a href="{i}">{i}</a>' for i in html]))
server.error_message_format = f'<style>{GetStyleSheet()}</style>' + server.error_message_format
# Adds the style sheet to the error page

print('Serving...http://localhost:3310')
server.serve_forever()