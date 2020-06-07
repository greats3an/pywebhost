from ..handler import RequestHandler
class AdapterConfidence:
    '''
        A pack of confidence mapping types
    '''
    @staticmethod
    def const(request,weights : int):
        '''
            Returns a constant value that DOES NOT change not matter what happens
            
            -   For example:

                weights = {
                    Confidence.const : 1
                }
        '''
        return weights

    @staticmethod
    def headers(request,weights : dict):
        '''
            Confidence that are `headers` weighted,passes header
        
            value to the **lambda** check

            -   For example (Websocket confidence):

                weights = {
                    Confidence.headers : {
                        'Sec-WebSocket-Key':1
                    }
                }            
        '''
        confidence = 0.00
        headers = dict(request.headers)
        for header,value in headers.items():
            if header in weights.keys():
                confidence += weights[header](value)
        return confidence
    @staticmethod
    def commmand(request,weights : dict):
        '''
            Confidence that are `command` weighted,passes command (GET,POST,OPTION,etc)
        
            to a integer

            -   For example (Webdav confidence):

                weights = {
                    Confidence.command : {
                        'COPY' : 1,
                        'CUT'  : 1,
                        'DEL'  : 1
                    } 
                }
                - Note that the command should always be CAPITAL
        '''
        confidence = weights[request.command] if request.command in weights.keys() else 0
        return confidence

    @staticmethod
    def scheme(request,weights : dict):
        '''
            Confidence that are `scheme` weighted,passes scheme
        
            to a integer

            -   For example (Websocket confidence):

                weights = {
                    Confidence.scheme : {
                        'ws' : 1
                    } 
                }
                - Note that the scheme should always be non-capital
        '''
        confidence = weights[request.scheme] if request.scheme in weights.keys() else 0
        return confidence

class Adapter():
    @staticmethod
    def __confidence__(request,weights):
        '''
            Base `confidence` method,approximates how well will the apdapter fit
            the request

            `request`   :   A `RequestHandler` Object

            `weights`   :   `Dict` with `Confidence` method as keys,see `Confidence` module for help
        '''
        confidence = 0.00
        for m_confidence in weights.keys():
            confidence += m_confidence(request,weights[m_confidence])
        return confidence

    def __init__(self,request:RequestHandler,ignore_confidence=False):
        '''Initiaztes the adapter with given request
        
           Use `ignore_confidence=True` to bypass `confidence` checking
        '''
        self.request = request
        if not ignore_confidence and self.__confidence__(request) < 0.3:
            '''Raise an exception if the confidence is too low'''
            raise Exception("Confidence for '%s' is too low (%s)" % (self.__name__,self.__confidence__(request)))
        return

    def send(self,message):
        '''I/O Output method,needs to be overriden'''
        pass

    def receive(self,message):
        '''I/O Input method,needs to be overriden'''
        pass

import os
__all__ = [i[:-3] for i in os.listdir(os.path.dirname(__file__)) if i[-2:] == 'py' and i != '__init__.py']
from . import *