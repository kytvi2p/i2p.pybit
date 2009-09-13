"""
Copyright 2009  Blub

Messages.py, a collection of functions to create and parse bittorrent messages.
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

from Conversion import longIntToBinary, shortIntToBinary, binaryToLongInt, binaryToShortInt, binToBinary, binaryToBin


##internal functions

def _createMessageLength(length):
    return longIntToBinary(length)


##messages

def generateKeepAlive():
    return _createMessageLength(0)


def generateChoke():
    return _createMessageLength(1)+shortIntToBinary(0)


def generateUnChoke():
    return _createMessageLength(1)+shortIntToBinary(1)


def generateInterested():
    return _createMessageLength(1)+shortIntToBinary(2)


def generateNotInterested():
    return _createMessageLength(1)+shortIntToBinary(3)


def generateHave(pieceIndex):
    return _createMessageLength(5)+shortIntToBinary(4)+longIntToBinary(pieceIndex)


def generateBitfield(bitfield):
    bitfield = binToBinary(bitfield)
    return _createMessageLength(1+len(bitfield))+shortIntToBinary(5)+bitfield


def generateRequest(index, begin, length):
    return _createMessageLength(13)+shortIntToBinary(6)+\
           longIntToBinary(index)+\
           longIntToBinary(begin)+\
           longIntToBinary(length)


def generatePiece(index, begin, block):
    return _createMessageLength(9+len(block))+shortIntToBinary(7)+\
           longIntToBinary(index)+\
           longIntToBinary(begin)+\
           block


def generateCancel(index, begin, length):
    return _createMessageLength(13)+shortIntToBinary(8)+\
           longIntToBinary(index)+\
           longIntToBinary(begin)+\
           longIntToBinary(length)


def generateHandshake(infoHash, peerId):
    return shortIntToBinary(19)+'BitTorrent protocol'+\
           (8*shortIntToBinary(0))+\
           infoHash+peerId
        

def getMessageLength(message):
    length = None
    if len(message)>=4:
        #length is decodeable...
        length = binaryToLongInt(message[:4])
    return length


def decodeShortHandshake(message):
    length = binaryToShortInt(message[0])
    proto = message[1:20]
    reserved = message[20:28]
    infoHash = message[28:48]
    return length, proto, reserved, infoHash

def decodeHandshake(message):
    length = binaryToShortInt(message[0])
    proto = message[1:20]
    reserved = message[20:28]
    infoHash = message[28:48]
    peerId = message[48:68]
    return length, proto, reserved, infoHash, peerId
    
def decodeMessage(message):
    length = binaryToLongInt(message[:4])
    if length==0:
        #keepalive
        result = (-1, None)
    else:
        numericMessageTyp = binaryToShortInt(message[4])  
        if numericMessageTyp<0 or numericMessageTyp>8:
            #unknown messagetype
            result = (-2, None)
        elif numericMessageTyp>=0 and numericMessageTyp<=3 and length==1:
            #choke, unchoke, interested, notinterested
            result = (numericMessageTyp, None)
        elif numericMessageTyp==4 and length==5:
            #have
            result = (numericMessageTyp, binaryToLongInt(message[5:9]))
        elif numericMessageTyp==5:
            #bitfield
            result = (numericMessageTyp, binaryToBin(message[5:]))
        elif numericMessageTyp==6 and length==13:
            #request
            result = (numericMessageTyp, (binaryToLongInt(message[5:9]),\
                                          binaryToLongInt(message[9:13]),\
                                          binaryToLongInt(message[13:17])))
        elif numericMessageTyp==7:
            #piece
            result = (numericMessageTyp, (binaryToLongInt(message[5:9]),\
                                          binaryToLongInt(message[9:13]),\
                                          message[13:]))
        elif numericMessageTyp==8 and length==13:
            #cancel
            result = (numericMessageTyp, (binaryToLongInt(message[5:9]),\
                                          binaryToLongInt(message[9:13]),\
                                          binaryToLongInt(message[13:17])))
        else:
            #corrupt message
            result = (None, None)
    return result
