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



from cStringIO import StringIO
from random import randrange
from traceback import print_exc
from urllib import quote, unquote, quote_plus, unquote_plus
import os


class FileHandle:
    """
    Imitates a normal file but reopens and closes a real file handle for most function calls 
    in reality. Saves file descriptors in a tradeoff against performance, useful to manage hundreds of 
    files at the same time.
    """
    
    def __init__(self, filename):
        self.filename = filename
        self.position = 0
        
    def close(self):
        """
        this violates the specs because it allows reading and writing after the file was closed
        should be fixed - sometime in the feature
        """
        pass
        
    def create(self):
        fl = open(self.filename, 'wb')
        fl.close()
        self.position = 0
        
    def empty(self):
        fl = open(self.filename, 'wb')
        fl.close()
        self.position = 0
        
    def flush(self):
        pass
    
    def read(self, bytes=-1):
        fl = open(self.filename, 'rb')
        fl.seek(self.position)
        data = fl.read(bytes)
        self.position = fl.tell()
        fl.close()
        return data
    
    def readline(self, bytes=-1):
        fl = open(self.filename, 'rb')
        fl.seek(self.position)
        data = fl.readline(bytes)
        self.position = fl.tell()
        fl.close()
        return data
    
    def realines(self, sizehint=None):
        fl = open(self.filename, 'rb')
        fl.seek(self.position)
        if sizehint==None:
            data = fl.readlines()
        else:
            data = fl.readlines(sizehint)
        self.position = fl.tell()
        return data   
    
    def rewind(self):
        self.position = 0     
    
    def seek(self, offset, whence=0):
        if whence==0:
            self.position = offset
            
        elif whence==1:
            self.position += offset
            
        elif whence==2:
            fl = open(self.filename, 'rb')
            fl.seek(offset, 2)
            self.position = fl.tell()
            fl.close()
            
    def size(self):
        fl = open(self.filename, 'rb')
        fl.seek(0,2)
        size = fl.tell()
        fl.close()
        return size
            
    def tell(self):
        return self.position
    
    def touch(self):
        fl = open(self.filename, 'ab')
        fl.close()
            
    def truncate(self, size=None):
        if size is None:
            size = self.position
        fl = open(self.filename, 'ab')
        fl.truncate(size)
        fl.close()
    
    def write(self, data):
        fl = open(self.filename, 'ab')
        fl.seek(self.position)
        fl.write(data)
        self.position = fl.tell()
        fl.close()
        
    def writelines(self, sequence):
        fl = open(self.filename, 'ab')
        fl.seek(self.position)
        fl.writelines(sequence)
        self.position = fl.tell()
        fl.close()


class PseudoFile:
    def __init__(self, stringList=None, string=None):
        if string is None:
            string = ''.join(stringList)
        self.psFlSize = len(string)
        self.psFl = StringIO(string)
    
    def close(self):
        self.psFl.close()
        self.psFlSize = 0
        
    def read(self, bytes=-1):
        data = self.psFl.read(bytes)
        return data
    
    def seek(self, offset, whence=0):
        self.psFl.seek(offset, whence)
        
    def size(self):
        return self.psFlSize
    
    def tell(self):
        return self.psFl.tell()


def logTraceback():
    pseudoFile = StringIO()
    print_exc(file = pseudoFile)
    return pseudoFile.getvalue()


def encodeStrForPrinting(string):
    if type(string)==str:
        result = string
    else:
        result = string.encode('UTF-8', 'ignore')
    return result


def generateRandomBinary(length):
    return ''.join([chr(randrange(0,256)) for x in xrange(0, length)])


def quoteUnicode(uniString):
    return quote(uniString.encode('UTF-8')).decode('UTF-8', 'ignore')


def unquoteUnicode(uniString):
    return unquote(uniString.encode('UTF-8')).decode('UTF-8', 'ignore')


def quoteUnicodePlus(uniString):
    return quote_plus(uniString.encode('UTF-8')).decode('UTF-8', 'ignore')


def unquoteUnicodePlus(uniString):
    return unquote_plus(uniString.encode('UTF-8')).decode('UTF-8', 'ignore')


def normalisePath(path, absolute=False, case=False, expand=False, noRelative=False, noSymlinks=False):
    if case:
        path = os.path.normcase(path)
    if expand:
        path = os.path.expanduser(path)
    if noSymlinks:
        path = os.path.realpath(path)
    if noRelative:
        path = os.path.normpath(path)
    if absolute:
        path = os.path.abspath(path)
    if noRelative:
        path = os.path.normpath(path)
    return path