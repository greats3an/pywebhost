from ast import Bytes, parse
from codecs import decode
from http.client import CONTINUE, OK
from io import BufferedIOBase, BufferedReader, IOBase,BytesIO
from os import system
import types
from ..handler import Request
from http import HTTPStatus
import os,mimetypes,json,base64,select
from typing import Any, NamedTuple, Type

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
            def RequestWrapper(request : Request,previous_prefix_result=None):
                prefix_result   = prefix  (request,previous_prefix_result) if prefix else previous_prefix_result
                function_result = function(request,prefix_result)
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

def streamcopy(from_:IOBase,to_:IOBase,size=-1,chunk_size=163840):
    '''[summary]

    Args:
        from_ (IOBase): [description]
        to_ (IOBase): [description]
        size (int, optional): [description]. Defaults to -1.
        chunk_size (int, optional): [description]. Defaults to 163840.

    Returns:
        [type]: [description]
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

def readstream(request):
    buffer = BytesIO()
    length = request.headers.get('Content-Length')
    assert length # this header musn't be empty : https://tools.ietf.org/html/rfc2616#page-33
    streamcopy(request.rfile,buffer,length)
    buffer.seek(0)
    decoded = buffer.read()
    return decoded

def writestream(request,data):
    buffer  = BytesIO(any2bytes(data))
    sent    = streamcopy(buffer,request.wfile)
    return sent

def Redirect(request:Request,redirect_to:str,code:int = HTTPStatus.FOUND) -> None:
    '''[summary]

    Args:
        redirect_to (str): [description]
        code (int, optional): [description]. Defaults to HTTPStatus.FOUND.
    '''
    request.send_response(code)
    request.send_header('Location',redirect_to)
    request.end_headers()

def ReadContentTo(request:Request,stream_to:IOBase,chunk_size : int=163840):
    length = request.headers.get('Content-Length')
    assert length # this header musn't be empty : https://tools.ietf.org/html/rfc2616#page-33
    return streamcopy(request.rfile,stream_to,length,chunk_size)

    return prefix , None

def WriteStaticContent(
    request : Any,
    object:Any,
    partial_acknowledge : bool=True,
    length : int=-1,
    chunk_size : int=163840,
    mime_type : str='text/plain') -> None:

    # deciding stream
    if isinstance(object,str):
        # str - file path
        stream = open(object,'rb')
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
        if not Range[:6] == 'bytes=' : return request.send_error(503,'Only ranges of `bytes` are supported')
        start,end = Range[6:].split('-')
        start,end = int(start if start else 0),int(end if end else length)
        if not (start >= 0 and start < length and end > 0 and end > start and end <= length):
            # Range not satisfiable
            return request.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
        
        request.clear_header() # re-constructs headers
        request.send_response(HTTPStatus.PARTIAL_CONTENT)
        request.send_header('Accept-Ranges','bytes')
        request.send_header('Content-Length',str(end - start))
        request.send_header('Content-Type',mime_type)
        request.send_header('Content-Range','bytes %s-%s/%s' % (start,end,length))
        request.end_headers()          

        stream.seek(start)
        streamcopy(stream,request.wfile,end - start,chunk_size=chunk_size)
        return True
    
    if partial_acknowledge:
        if length > 0:
            request.send_header('Accept-Ranges','bytes')
            if send_range(request):return True
    send_once()

@ModuleWrapper
def VerbRestrictionWrapper(verbs : list = ['GET','POST']) -> None:
    '''[summary]

    Args:
        verbs (list, optional): [description]. Defaults to ['GET','POST'].
    '''
    def prefix(request,previous_suffix):
        '''Restricts HTTP Verbs,does nothing if the verb is in the `verbs` list'''
        if not request.command in verbs:
            raise Exception('Verb %s is not allowed' % request.command)
    return prefix , None

@ModuleWrapper
def BinaryMessageWrapper(read=True,write=True):
    def prefix(request,previous_prefix_result):
        if not read:return None
        binary = readstream(request) if previous_prefix_result is None else previous_prefix_result    
        return binary
    def suffix(request,function_result):
        if function_result:
            binary = any2bytes(function_result)
            if write:writestream(request,binary)
            return function_result
        return bytearray()
    return prefix , suffix

@ModuleWrapper
def JSONMessageWrapper(decode=True,encode=True,read=True,write=True):
    def prefix(request,previous_prefix_result):
        if not read:return None
        string = any2str(readstream(request)) if previous_prefix_result is None else previous_prefix_result
        return string if not decode else json.loads(string)
    def suffix(request,function_result):
        if function_result and encode:
            string = json.dumps(function_result)
            if write:writestream(request,string)
            return string
        elif function_result:
            return function_result
        else:
            return None
    return prefix , suffix

@ModuleWrapper
def Base64MessageWrapper(decode=True,encode=True,read=True,write=True):
    def prefix(request,previous_prefix_result):
        if not read:return None
        binary = any2str(readstream(request)) if previous_prefix_result is None else previous_prefix_result
        return binary if not decode else base64.b64decode(binary)
    def suffix(request,function_result):
        if function_result and encode:
            binary = base64.b64encode(function_result.encode())
            if write:writestream(request,binary)
            return binary
        elif function_result:
            return function_result
        else:
            return None
    return prefix , suffix