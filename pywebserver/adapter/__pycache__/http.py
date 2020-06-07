'''
# HTTP Protocol

Yes,I know that Websockets are under the hierarchy of HTTP protocol,
But this is just for the ease of use for future protocols to be supplied (like WebDav)

Every thing this server offers are HTTP-Based,while the parent module offers a `Protocol` class,
it's too abstract to be any useful
'''

import os
from . import Adapter,Confidence
class HTTP(Adapter):
    '''
    HTTP Adapter Object

    Offers handy tools for handling HTTP stuff
    '''
    @staticmethod
    def __confidence__(request) -> float:
        '''For HTTP,always have 0.5 of confidence'''
        return super(HTTP,HTTP).__confidence__(request,{            
            Confidence.const:0.5
        })

    def __init__(self,request:RequestHandler):
        '''Initializes the instance'''
        super().__init__(request)
    
    def send(self,message):
        '''Directly sends block of data with `wfile`'''
        return self.request.wfile.write(message)
    
    def read(self):
        '''Directly reads ALL data with `rfile`'''
        return self.request.wfile.read()