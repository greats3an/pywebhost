class Confidence:
    '''
        A pack of confidence mapping methods
    '''
    @staticmethod
    def const(handler,base_weight : int):
        '''Returns a constant value that DOES NOT change not matter what happens'''
        return base_weight

    @staticmethod
    def headers(handler,header_weight : dict):
        '''
            Confidence that are `headers` weighted,passes header
        
            value to the lambda check
        '''
        confidence = 0.00
        headers = dict(handler.headers)
        for header,value in headers.items():
            if header in header_weight.keys():
                confidence += header_weight[header](value)
        return confidence
    @staticmethod
    def commmand(handler,command_weight : dict):
        '''
            Confidence that are `command` weighted,passes command (GET,POST,OPTION,etc)
        
            value to the lambda check
        '''
        confidence = 0.00
        for command,checker in command_weight.items():
           if handler.command == command:confidence += checker(command)
        return confidence

class Protocol():
    @staticmethod
    def __confidence__(handler,weights):
        '''
            Base `confidence` method
        '''
        confidence = 0.00
        for m_confidence in weights.keys():
            confidence += m_confidence(handler,weights[m_confidence])
        return confidence
    @staticmethod
    def __handle__(handler):
        pass
import os
__all__ = [i[:-3] for i in os.listdir(os.path.dirname(__file__)) if i[-2:] == 'py' and i != '__init__.py']
from . import *