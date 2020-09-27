from ..handler import Request

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

    request : Request
    '''Request object'''
    @staticmethod
    def __confidence__(request,weights={AdapterConfidence.const:1}):
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

    def __init__(self,request:Request,ignore_confidence=False):
        '''
        Provides basic Adapter model

        Base class proivdes basic HTTP functions,like `send` arbitary data to the client with the correct headers (you may do this by hand otherwise)
        
        The `__confidence__` is the base method for checking if a request can be adapted into such Adapter,use it like the example given below:
        
            class MyAdapter(Adapter):
                @staticmethod
                def __confidence__(request) -> float:        
                    return super(Websocket,Websocket).__confidence__(request,{
                        AdapterConfidence.headers:{
                            'Sec-WebSocket-Key':lambda v:1 if v and len(v) > 8 else 0
                        },
                    })
            ...
        '''
        if isinstance(request,Adapter):
            # For adpating from Adpter to Adapters
            self.request = Adapter.request
        else:self.request = request
        # Stores the request
        if not ignore_confidence and self.__confidence__(request) < 0.3:
            '''Raise an exception if the confidence is too low'''
            raise Exception("Confidence for '%s' is too low (%s)" % (type(self).__name__,self.__confidence__(request)))
        return

    def send(self,message,code=200,code_message=''):
        '''Send a `str` / `bytearray` object to the client and flushes headers

            message     :   the object
            code        :   HTTP Response code
            code_message:   Extra Message for this HTTP response
        '''
        self.request.send_response(code,code_message)
        self.request.end_headers()
        self.request.wfile.write(str(message).encode() if type(message) != bytes else message)
        self.request.wfile.flush()

    def receive(self,message):
        '''Receive arbitary amount of data from the client,reserved for other adapters'''
        pass