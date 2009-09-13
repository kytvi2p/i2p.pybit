"""
Copyright 2009  Blub

Bencoding.py, a collection of classes for encoding and decoding data according to the basic
Bittorrent "bencoding" Standard and another extended version of that Standard..
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


##encode

def _bencode(obj):
    #bittorrent bencode
    #Supports: dicts, lists, ints and strings
    #May store: dicts, lists, ints, longs and strings
    result = deque()
    if type(obj)==dict:
        #dict
        result.append('d')
        keys = obj.keys()
        keys.sort()
        for i in keys:
            result.append(_bencode(i))
            result.append(_bencode(obj[i]))
        result.append('e')
        
    elif type(obj)==list:
        #list or tuple
        result.append('l')
        for i in obj:
            result.append(_bencode(i))
        result.append('e')
        
    elif type(obj)==int or type(obj)==long:
        #int or long
        result.append('i')
        result.append(str(obj))
        result.append('e')
        
    elif type(obj)==str:
        #string
        result.append(str(len(obj)))
        result.append(':')
        result.append(obj)
        
    else:
        raise Exception('Encountered unsupported element of type "'+str(type(obj))+'"!')
    
    return ''.join(result)


def _bencodeExt(obj):
    #extended bencode
    #Supports: dicts, sets, lists, tuples, ints, floats, bools, None, strings and unicode strings
    #May store: dicts, sets, lists, tuples, ints, longs, floats, bools, None, strings and unicode strings
    result = deque()
    if type(obj)==dict:
        #dict
        result.append('d')
        keys = obj.keys()
        keys.sort()
        for i in keys:
            result.append(_bencodeExt(i))
            result.append(_bencodeExt(obj[i]))
        result.append('e')
        
    elif type(obj)==set:
        #set
        result.append('s')
        for i in sorted(obj):
            result.append(_bencodeExt(i))
        result.append('e')
        
    elif type(obj)==list:
        #list
        result.append('l')
        for i in obj:
            result.append(_bencodeExt(i))
        result.append('e')
        
    elif type(obj)==tuple:
        #tuple
        result.append('t')
        for i in obj:
            result.append(_bencodeExt(i))
        result.append('e')
        
    elif type(obj)==int or type(obj)==long:
        #int or long
        result.append('i')
        result.append(str(obj))
        result.append('e')
        
    elif type(obj)==float:
        #float
        result.append('f')
        result.append(str(obj))
        result.append('e')
        
    elif type(obj)==bool:
        #bool
        result.append('b')
        result.append(str(obj))
        result.append('e')
        
    elif obj is None:
        #None
        result.append('n')
        
    elif type(obj)==str:
        #string
        result.append(str(len(obj)))
        result.append(':')
        result.append(obj)
        
    elif type(obj)==unicode:
        #unicode string
        result.append('u')
        encStr = obj.encode('UTF-8')
        result.append(str(len(encStr)))
        result.append(':')
        result.append(encStr)
        
    else:
        #something unsupported
        raise Exception('Encountered unsupported element of type "'+str(type(obj))+'"!')
    
    return ''.join(result)


def bencode(obj, extended=False):
    if extended:
        result = _bencodeExt(obj)
    else:
        result = _bencode(obj)
    
    return result


##decode


def _bdecode(encObj, place = 0):
    #bittorrent bdecode
    #Supports: dicts, lists, ints and strings
    if encObj[place]=='d':
        #dict
        place += 1
        result = {}
        while not encObj[place]=='e':
            key, place = _bdecode(encObj, place)
            value, place = _bdecode(encObj, place)
            result[key] = value
        place += 1
        
    elif encObj[place]=='l':
        #dict
        place += 1
        result = []
        while not encObj[place]=='e':
            value, place = _bdecode(encObj, place)
            result.append(value)
        place += 1
        
    elif encObj[place]=='i':
        #int
        place += 1
        end = encObj.find('e', place)
        result = int(encObj[place:end])
        place = end + 1
        
    else:
        #string
        collon = encObj.find(':', place)
        length = int(encObj[place:collon])
        place = collon + 1
        result = encObj[place:place+length]
        place += length
    
    return result, place


def _bdecodeExt(encObj, place = 0):
    #extended bdecode
    #Supports: dicts, sets, lists, tuples, ints, floats, bools, None, strings and unicode strings
    if encObj[place]=='d':
        #dict
        place += 1
        result = {}
        while not encObj[place]=='e':
            key, place = _bdecodeExt(encObj, place)
            value, place = _bdecodeExt(encObj, place)
            result[key] = value
        place += 1
        
    elif encObj[place]=='s':
        #set
        place += 1
        result = set()
        while not encObj[place]=='e':
            value, place = _bdecodeExt(encObj, place)
            result.add(value)
        place += 1
        
    elif encObj[place]=='l':
        #list
        place += 1
        result = []
        while not encObj[place]=='e':
            value, place = _bdecodeExt(encObj, place)
            result.append(value)
        place += 1
        
    elif encObj[place]=='t':
        #tuple
        place += 1
        result = deque()
        while not encObj[place]=='e':
            value, place = _bdecodeExt(encObj, place)
            result.append(value)
        result = tuple(result)
        place += 1
        
    elif encObj[place]=='i':
        #int
        place += 1
        end = encObj.find('e', place)
        result = int(encObj[place:end])
        place = end + 1
        
    elif encObj[place]=='f':
        #float
        place += 1
        end = encObj.find('e', place)
        result = float(encObj[place:end])
        place = end + 1
        
    elif encObj[place]=='b':
        #bool
        place += 1
        end = encObj.find('e', place)
        result = bool(encObj[place:end])
        place = end + 1
        
    elif encObj[place]=='n':
        #None
        place += 1
        result = None
        
    elif encObj[place]=='u':
        #unicode string
        place += 1
        collon = encObj.find(':', place)
        length = int(encObj[place:collon])
        place = collon + 1
        result = encObj[place:place+length].decode('UTF-8')
        place += length
        
    else:
        #normal string
        collon = encObj.find(':', place)
        length = int(encObj[place:collon])
        place = collon + 1
        result = encObj[place:place+length]
        place += length
    
    return result, place


def bdecode(encObj, extended=False):
    if extended:
        result = _bdecodeExt(encObj, 0)[0]
    else:
        result = _bdecode(encObj, 0)[0]
    return result