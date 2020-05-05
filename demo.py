from pywebserver.handler import HTTPRequestHandler
from pywebserver.proto import http,websocket
from pywebserver import PyWebServer
import logging,coloredlogs,base64,sys

if len(sys.argv) < 2:
    print('usage:	demo.py [address] [port]')
    print('Program will now use default address and port')
    sys.argv = (sys.argv[0],'localhost',3331)
coloredlogs.install(logging.DEBUG)
server = PyWebServer(
    (sys.argv[1],int(sys.argv[2])),
    protos=[http.HTTP,websocket.Websocket]
)

# Websocket Echo Server
@server.path_absolute('GET','/',websocket.Websocket)
def WebsocketEchoServer(handler: HTTPRequestHandler):
    # Accepts the reqeust
    session = handler.proto
    session.handshake()
    def callback_receive(frame):
        print('New message from %s:%s:%s' % (*handler.client_address, frame[-1].decode()))
        session.send(b'OK.' + frame[-1])
    session.callback_receive = callback_receive
    session.run()
@server.path_absolute('GET','/favicon.ico',http.HTTP)
def Favicon(handler: HTTPRequestHandler):
    favicon_base64 = '''iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAAEnQAABJ0Ad5mH3gAAABXSURBVDhPpc1LDsBACALQuf+lrQ2EMpr059tMhNCu+OgcrB2Lhjk6HOkqLHR/B45FwxyPqChmgzwci4Y5nvfGf1BRzAZ5OBSFcg5w3KgDh6JQ/vztTcQBqP4l98/X4gAAAAAASUVORK5CYII='''
    handler.send_response(200)
    handler.send_header('Content-Type','image/x-icon')
    handler.end_headers()
    http.Modules.write_string(handler.proto,base64.b64decode(favicon_base64))

def GetStyleSheet():
    return '''*{font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;font-size: 16px;  }body {margin: 1em;background-color: #2d2d2d;}a {color: #666;text-decoration: none;transition: all 0.1s linear;}a:hover {color: #ffcc66;}h1 {color: #CCC;font-size: 32px;}h3 {color: #AAA;font-size: 24px;}pre {overflow: auto;margin: 1em;line-height: 2em;}'''

# Welcome page
@server.path_absolute('GET','/',http.HTTP)
def Index(handler: HTTPRequestHandler):
    handler.send_response(200)
    handler.send_header('Content-Type', 'text/html;encoding=utf-8')
    handler.end_headers()
    http.Modules.write_string(handler.proto,f'''    
        <head><style>{GetStyleSheet()}</style>
        <link rel="icon" type="image/png" href="favicon.ico">
        <title>PyWebServer Landing Page</title></head>
        <h1>Welcome to PyWebServer!</h1>
        <h3>For Websocket ECHO Server:</h3>
        <a href="ws://{server.server_address[0]}:{server.server_address[1]}">ws://{server.server_address[0]}:{server.server_address[1]}</a>
        <h3>For File Explorer:</h3>
        <a href="files">http://{server.server_address[0]}:{server.server_address[1]}/files</a>
    '''.encode())
    handler.wfile.flush()

# Test folder,with custom stylesheet
def IndexFolderWithStyleSheet(*a,**k):
    return http.Modules.index_folder(*a,**k,stylesheet=GetStyleSheet())

server.add_relative(
    'GET','/files',http.HTTP,
    {
        'file':http.Modules.write_file,
        'folder':IndexFolderWithStyleSheet
    },local=r'.'
)

logging.info('Now serving... %s:%s' % server.server_address)
server.serve_forever()