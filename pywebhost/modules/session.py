from codecs import decode
from http.client import CONTINUE, OK
from io import BufferedIOBase, BufferedReader, IOBase,BytesIO
from os import system
import pywebhost
from pywebhost.adapter.websocket import Websocket
import types
from ..handler import Request
from http import HTTPStatus
import os,mimetypes,json,base64,select
from typing import Any, NamedTuple, Type, Union

class Session():
    '''https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies'''
    @property
    def session_id(self):
        return self.request.coo
    
    def __init__(self,request : Request) -> None:
        self.request = request
