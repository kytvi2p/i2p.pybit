"""
Copyright 2009  Blub

Utilities.py, a collection of helpful functions and simple classes.
This file is part of PyBit.

PyBit is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published
by the Free Software Foundation, version 2 of the License.

PyBit is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with PyBit.  If not, see <http://www.gnu.org/licenses/>.
"""

from collections import deque
from cStringIO import StringIO
from traceback import print_exc

import wx


def logTraceback():
    pseudo_file = StringIO()
    print_exc(file = pseudo_file)
    return pseudo_file.getvalue()


def encodeStrForPrinting(string):
    if type(string)==str:
        result = string
    else:
        result = string.encode('UTF-8', 'ignore')
    return result


def showWarningMessage(parent, text, *args, **kw):
    title = kw.get('title', 'Warning')
    wx.MessageBox(text % args, title, style=(wx.OK | wx.ICON_EXCLAMATION), parent=parent)


def showErrorMessage(parent, text, *args, **kw):
    title = kw.get('title', 'Error')
    wx.MessageBox(text % args, title, style=(wx.OK | wx.ICON_ERROR), parent=parent)


class FunctionCallConverter:
    def __init__(self, func, funcArgs=[], funcKw={}, resultFilter=None, resultFilterFormat=None):
        self.func = func
        self.funcArgs = funcArgs
        self.funcKw = funcKw
        
        self.resultFilter = resultFilter
        self.resultFilterFormat = resultFilterFormat
        
        
    def _getResult(self, orgResult, filter):
        if type(filter) == str:
            result = orgResult[filter]
        
        else:
            result = orgResult
            for key in filter:
                result = result[key]
        return result
    
    
    def call(self, *args, **kw):
        funcArgs = self.funcArgs + args
        funcKw = self.funcKw.copy().update(kw)
        apply(self.func, self.funcArgs, self.funcKw)
        
        
    def callForValue(self, *args, **kw):
        funcArgs = self.funcArgs + list(args)
        funcKw = self.funcKw.copy().update(kw)

        orgResult = apply(self.func, self.funcArgs, self.funcKw)
        
        if self.resultFilter is None:
            result = orgResult
            
        else:
            if self.resultFilterFormat == 'dict':
                result = {}
                for key in self.resultFilter:
                    if type(key) == str:
                        result[key] = orgResult[key]
                    else:
                        result[key[-1]] = self._getResult(orgResult, key)
            
            elif self.resultFilterFormat == 'list':
                result = []
                for key in self.resultFilter:
                    result.append(self._getResult(orgResult, key))
                        
            elif self.resultFilterFormat == 'deque':
                result = deque()
                for key in self.resultFilter:
                    result.append(self._getResult(orgResult, key))
                        
            elif self.resultFilterFormat == 'item':
                result = self._getResult(orgResult, self.resultFilter)
                
        return result