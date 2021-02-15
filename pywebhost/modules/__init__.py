from codecs import decode
from http.client import CONTINUE, OK
from io import BufferedIOBase, BufferedReader, IOBase,BytesIO
from os import system
import time
from ..handler import Request
from http import HTTPStatus
import os,mimetypes,json,base64,select
from typing import Any, NamedTuple, Type, Union

class BadRequestException(Exception):
    '''Exception with code and explaination'''
    def __init__(self,code,explain=None) -> None:
        self.code = code
        self.explain = explain
        super().__init__(explain)

def ModuleWrapper(provider):    
    '''Base circlular wrapper support func

    Args:
        provider (function)

    Usage:
    - As a module
    @ModuleWrapper
    def dummy_func(dummy_arg):
        def prefix(request,previous_prefix_result):
            ...
        def suffix(request,function_result):
            ...
        return prefix,suffix
    - As a wrapped module
    @dummy_func(dummy_arg=42)
    def dummy_request(request,content):
        ...

    # provider
     A function,that when called with arguments,always returns tuple (prefix,suffix) of functions:
    - prefix : what to execute when called by server
        - takes two arguments : `request` (Request) , `previous_prefix_result`
            - `request` is what it is,represented by the `pywebhost.Request` object
            - `previous_prefix_result` is the result of the prefix function of the previous wrapper
        - returns a value , which is used by the function wrapped by `RequestFunctionWrapper`
    - suffix : what to do after the `RequestFunctionWrapper` is finished
        - takes two arguments : `request` (Request) , `function_result`
            - `request` is what it is,represented by the `pywebhost.Request` object
            - `function_result` is the result of the function wrapped
        - returns a value , which , if chained with another wrapper , will be its `function_result`
    '''
    def UserWrapper(*a,**k):
        prefix,suffix = provider(*a,**k)
        def RequestFunctionWrapper(function):
            def RequestWrapper(initator : object,request : Request,previous_prefix_result=None):                
                prefix_result   = prefix  (request,previous_prefix_result) if prefix else previous_prefix_result
                function_result = function(initator,request,prefix_result)
                suffix_result   = suffix  (request,function_result) if suffix else function_result
                return suffix_result
            return RequestWrapper
        return RequestFunctionWrapper
    return UserWrapper

def any2bytes(any):
    if isinstance(any,str):return any.encode()
    return bytearray(any)

def any2str(any):
    if isinstance(any,bytearray) or isinstance(any,bytes):return decode(any)
    return str(any)

def filesize(path):
    return os.path.getsize(path)

def streamcopy(from_:IOBase,to_:IOBase,size=-1,chunk_size=163840):
    '''Copies content from one buffer to the other,chunk by chunk

    NOTE: Nor from_ or to_ has to be IOBase objects,it's doable as long as they have read() / write() calls
    
    Args:
        from_ (IOBase): Stream to copy from
        to_ (IOBase): Stream to copy to
        size (int, optional): Length to be copied. Defaults to -1.
        chunk_size (int, optional): Size of chunk. Defaults to 163840.

    Returns:
        int : copied length
    '''
    if not size:return 0
    size,copied = int(size),0
    if size < 0:
        # read until EOF
        def copychunk():
            chunk = from_.read(chunk_size)
            if not chunk:return 0
            to_.write(chunk)
            return len(chunk)
        while (True):
            copied_ = copychunk()
            if not copied_:break
            copied+=copied_                
    else:
        # read `size` of bytes
        for offset in range(0,size,chunk_size):
            remaining = size - offset 
            chunk = from_.read(remaining if remaining < chunk_size else chunk_size)
            if not chunk:break
            copied += len(chunk)
            to_.write(chunk)
    return copied

def readstream(request:Request):
    '''Reads all the content from client

    Args:
        request (Request): Request

    Raises:
        BadRequestException: When `Content-Length` is not defined

    Returns:
        bytes : Read content
    '''
    buffer = BytesIO()
    length = request.headers.get('Content-Length')
    if not length:return b'' # this header musn't be empty : https://tools.ietf.org/html/rfc2616#page-33
    streamcopy(request.rfile,buffer,length)
    buffer.seek(0)
    return buffer.read()

def writestream(request:Request,data):
    '''Writes content to client

    Args:
        request (Request): Request
        data (Any): bytes / str like objects

    Returns:
        int : Bytes written
    '''
    buffer  = any2bytes(data)
    request.send_header('Content-Length',str(len(buffer)))
    request.end_headers()    
    sent    = streamcopy(BytesIO(buffer),request.wfile)
    return sent

def Redirect(request:Request,redirect_to:str,code:int = HTTPStatus.FOUND) -> None:
    '''Redirects request to another URL

    Args:
        redirect_to (str): Where to redirect to
        code (int, optional): MOVED_PERMANENTLY or FOUND. Defaults to HTTPStatus.FOUND.
    '''
    request.send_response(code)
    request.send_header('Location',redirect_to)
    request.end_headers()

def ReadContentToBuffer(request:Request,stream_to:IOBase,chunk_size : int=163840):
    '''Reads content of request to buffer

    Args:
        request (Request): Request
        stream_to (IOBase): Where to write to
        chunk_size (int, optional): Size of chunk. Defaults to 163840.

    Returns:
        int : Read bytes
    '''
    length = request.headers.get('Content-Length')
    assert length # this header musn't be empty : https://tools.ietf.org/html/rfc2616#page-33
    return streamcopy(request.rfile,stream_to,length,chunk_size)

def WriteContentToRequest(
    request : Request,
    object:Union[str,bytes,bytearray],
    partial_acknowledge : bool=False,
    length : int=-1,
    chunk_size : int=163840,
    mime_type : str='text/plain') -> None:
    '''Writes buffer / file as static content to stream

    Args:
        request (Request): Request
        object (Union[str,bytes,bytearray]): Content to be sent
        partial_acknowledge (bool, optional): React to HTTP 206s or not. Defaults to False.
        length (int, optional): The length to be sent. Defaults to -1.
        chunk_size (int, optional): Size of chunk. Defaults to 163840.
        mime_type (str, optional): Content mime type. Defaults to 'text/plain'.

    Returns:
        int : Bytes sent
    '''
    # serializing stream
    if isinstance(object,str):
        # str - file path
        length = filesize(object) if length < 0 else length
        stream = open(object,'rb')
    elif isinstance(object,(bytes,bytearray)):
        length = len(object)
        stream = BytesIO(object)
    elif hasattr(object,'read'):
        # readable - IO-like objects
        stream = object
        
    def send_once(request):                        
        request.send_response(HTTPStatus.OK)   
        if length > 0:request.send_header('Content-Length',length)
        request.send_header('Content-Type',mime_type)
        request.end_headers()     
        streamcopy(stream,request.wfile,chunk_size=chunk_size)
        return True

    def send_range(request):
        Range = request.headers.get('Range')
        if not Range:return False # no range header
        if not Range[:6] == 'bytes=' : return request.send_error(HTTPStatus.BAD_REQUEST,'Only ranges of `bytes` are supported')
        start,end = Range[6:].split('-')
        start,end = int(start if start else 0),int(end if end else length)
        if not (start >= 0 and start < length and end > 0 and end > start and end <= length):
            # Range not satisfiable
            return request.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)

        request.send_response(HTTPStatus.PARTIAL_CONTENT)
        request.send_header('Content-Length',str(end - start))
        request.send_header('Content-Type',mime_type)
        request.send_header('Content-Range','bytes %s-%s/%s' % (start,end - 1,length))
        request.end_headers()          

        stream.seek(start)
        streamcopy(stream,request.wfile,end - start,chunk_size=chunk_size)
        return True
    
    if partial_acknowledge:
        if length > 0:
            request.send_header('Accept-Ranges','bytes')
            if send_range(request):                
                return True
    return send_once(request)

@ModuleWrapper
def VerbRestrictionWrapper(verbs : list = ['GET','POST']) -> None:
    '''Wrapper to limit request to a certain range of verbs

    When request's verb is not in the list,a HTTP 400 will be responded instead

    Usage:

        ...
        @server.route('/api/get_v1')
        @VerbRestrictionWrapper(['POST'])
        def get(request : Request,content):
            ...

    Args:
        verbs (list, optional): [description]. Defaults to ['GET','POST'].
    '''
    def prefix(request,previous_suffix):
        '''Restricts HTTP Verbs,does nothing if the verb is in the `verbs` list'''
        if not request.command in verbs:
            raise BadRequestException(HTTPStatus.BAD_REQUEST,'Verb %s is not allowed' % request.command)
    return prefix , None

@ModuleWrapper
def BinaryMessageWrapper(read=True,write=True):
    '''Wrapper to receive,send binary content before,after the request
    
    Usage:
    
        @server.route('.*')        
        @BinaryMessageWrapper(read=True,write=True)
        def main(request:Request,content):
            return salteddigest(content)

    Args:
        read (bool, optional): Read the content. Defaults to True.
        write (bool, optional): Write the content. Defaults to True.
    '''
    def prefix(request,previous_prefix_result):
        if not read:return previous_prefix_result
        binary = readstream(request) if previous_prefix_result is None else previous_prefix_result    
        return binary
    def suffix(request,function_result):        
        binary = any2bytes(function_result)
        if write:
            writestream(request,binary)
        return function_result
        return bytearray()
    return prefix , suffix

@ModuleWrapper
def JSONMessageWrapper(decode=True,encode=True,read=True,write=True):
    '''Wrapper to receive,send JSON content before,after the request

    Usage:
    
        @server.route('.*')        
        @Base64MessageWrapper(decode=True,encode=False,read=True,write=False) # only decodes content
        @JSONMessageWrapper(decode=True,encode=True,write=True,read=False)    # parses decoded content,encodes return value,then writes it
        def main(request:Request,content):
            return {'data':'senstive_data_or_sth_idk'}


    Args:
        decode (bool, optional): To decode the request. Defaults to True.
        encode (bool, optional): To encode the response. Defaults to True.
        read (bool, optional): Read the content. Defaults to True.
        write (bool, optional): Write the content. Defaults to True.
    '''
    def prefix(request,previous_prefix_result):
        if not read:return previous_prefix_result
        string = any2str(readstream(request)) if previous_prefix_result is None else previous_prefix_result
        return string if not decode else json.loads(string)
    def suffix(request,function_result):
        string = function_result
        if encode:
            string = json.dumps(function_result)
        if write:
            writestream(request,string)
        return string
    return prefix , suffix

@ModuleWrapper
def Base64MessageWrapper(decode=True,encode=True,read=True,write=True):
    '''Wrapper to receive,send BASE64 content before,after the request

    Usage:
    
        @server.route('.*')
        @JSONMessageWrapper(decode=True,encode=False,write=False)     # only reads request as pass it as `content`
        @Base64MessageWrapper(decode=False,read=False)                # encodes the response and writes it
        def main(request:Request,content):
            return 'senstive_data_or_sth_idk'    


    Args:
        decode (bool, optional): To decode the request. Defaults to True.
        encode (bool, optional): To encode the response. Defaults to True.
        read (bool, optional): Read the content. Defaults to True.
        write (bool, optional): Write the content. Defaults to True.
    '''    
    def prefix(request,previous_prefix_result):
        if not read:return previous_prefix_result
        binary = any2str(readstream(request)) if previous_prefix_result is None else previous_prefix_result
        return binary if not decode else base64.b64decode(binary)
    def suffix(request,function_result):
        binary = function_result.encode()
        if encode:
            binary = base64.b64encode(binary)
        if write:
            writestream(request,binary)
        return binary   
    return prefix , suffix