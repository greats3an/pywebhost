from pywebserver.handler import HTTPRequestHandler
from pywebserver.proto import http,websocket
from pywebserver import PyWebServer
import logging,coloredlogs

coloredlogs.install(logging.DEBUG)
server = PyWebServer(
    ('localhost',3331),
    [http.HTTP,websocket.Websocket],
)

# Welcome page
@server.path_absolute('GET','/',http.HTTP)
def GET(handler: HTTPRequestHandler):
    handler.send_response(200)
    handler.send_header('Content-Type', 'text/html;encoding=utf-8')
    handler.end_headers()
    http.Modules.write_string(handler.proto,f'''
        <h1>Welcome to PyWebServer!</h1>
        <h3>For Websocket ECHO Server:</h3>
        <a href="ws://{server.server_address[0]}:{server.server_address[1]}">
        ws://{server.server_address[0]}:{server.server_address[1]}
        </a>
        <h3>For File Explorer:</h3>
        <a href="files">
        http://{server.server_address[0]}:{server.server_address[1]}/files
        </a>
    '''.encode())
    handler.wfile.flush()
# Websocket Echo Server
@server.path_absolute('GET','/ws',websocket.Websocket)
def WS(handler: HTTPRequestHandler):
    # Accepts the reqeust
    session = handler.proto
    session.handshake()
    def callback_receive(frame):
        print('New message from %s:%s:%s' % (*handler.client_address, frame[-1].decode()))
        session.send(b'OK.' + frame[-1])
    session.callback_receive = callback_receive
    session.run()
# Test folder
server.add_relative(
    'GET','/files',http.HTTP,
    {
        'file':http.Modules.write_file,
        'folder':http.Modules.index_folder
    },local=r'.'
)

logging.info('Now serving... %s:%s' % server.server_address)
server.serve_forever()