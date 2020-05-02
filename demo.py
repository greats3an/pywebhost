from handler import HTTPRequestHandler
from proto import http,websocket
from pywebserver import PyWebServer
import logging,coloredlogs

coloredlogs.install(logging.DEBUG)
server = PyWebServer(
    ('localhost',3331),
    [http.HTTP,websocket.Websocket],
)

# Welcome page
@server.path('GET','/',http.HTTP)
def GET(caller: HTTPRequestHandler):
    caller.send_response(200)
    caller.send_header('Content-Type', 'text/html;encoding=utf-8')
    caller.end_headers()
    caller.proto.write_string(f'''
        <h1>Welcome to PyWebServer!</h1>
        <h3>For Websocket ECHO Server:</h3>
        <a href="ws://{server.server_address[0]}:{server.server_address[1]}">
        ws://{server.server_address[0]}:{server.server_address[1]}
        </a>
    '''.encode())
    caller.wfile.flush()
# Websocket Echo Server
@server.path('GET','/ws',websocket.Websocket)
def WS(caller: HTTPRequestHandler):
    # Accepts the reqeust
    session = caller.proto
    session.handshake()
    def callback_receive(frame):
        print('New message from %s:%s:%s' % (*caller.client_address, frame[-1].decode()))
        session.send(b'OK.' + frame[-1])
    session.callback_receive = callback_receive
    session.run()
# Error test
@server.path('GET','/error',http.HTTP)
def ERROR(caller : HTTPRequestHandler):
# Directroy access
    caller.send_response(503)
    caller.end_headers()
server.directory('/','.')

logging.info('Now serving... %s:%s' % server.server_address)
server.serve_forever()