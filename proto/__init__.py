class Confidence:
    '''
        A pack of confidence mapping types
    '''
    @staticmethod
    def const(handler,weights : int):
        '''
            Returns a constant value that DOES NOT change not matter what happens
            
            -   For example:

                weights = {
                    Confidence.const : 1
                }
        '''
        return weights

    @staticmethod
    def headers(handler,weights : dict):
        '''
            Confidence that are `headers` weighted,passes header
        
            value to the **lambda** check

            -   For example (Websocket confidence):

                weights = {
                    Confidence.headers : {
                        'Sec-WebSocket-Key':lambda k:0.8 if len(k) > 8 else 0.1,
                        'Sec-WebSocket-Version':lambda v:0.1,
                        'Sec-WebSocket-Extensions':lambda e:0.1
                    }
                }            
        '''
        confidence = 0.00
        headers = dict(handler.headers)
        for header,value in headers.items():
            if header in weights.keys():
                confidence += weights[header](value)
        return confidence
    @staticmethod
    def commmand(handler,weights : dict):
        '''
            Confidence that are `command` weighted,passes command (GET,POST,OPTION,etc)
        
            value to the lambda check

            -   For example (Webdav confidence):

                weights = {
                    Confidence.command : {
                        'COPY' : 1,
                        'CUT'  : 1,
                        'DEL'  : 1
                    } 
                }
        '''
        confidence = weights[handler.command] if handler.command in weights.keys() else 0
        return confidence

class Protocol():
    @staticmethod
    def __confidence__(handler,weights):
        '''
            Base `confidence` method

            `handler`   :   A `HTTPRequestHandler` Object

            `weights`   :   `Confidence` method for determinating confidence
        '''
        confidence = 0.00
        for m_confidence in weights.keys():
            confidence += m_confidence(handler,weights[m_confidence])
        return confidence

    def __relative__(self,mapping):
        '''Handles the relative path'''
        return 0
import os
__all__ = [i[:-3] for i in os.listdir(os.path.dirname(__file__)) if i[-2:] == 'py' and i != '__init__.py']
from . import *