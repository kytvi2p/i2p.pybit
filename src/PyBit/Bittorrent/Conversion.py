"""
Copyright 2009  Blub

Conversion.py, a collection of functions to convert data into different formats.
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
from socket import inet_ntoa

import sha
import binascii


##binary

def binaryToPeer(binaryString):
    convIp = inet_ntoa(binaryString[0:4])
    convPort = binaryToLongInt(binaryString[4:6])
    return convIp, convPort


def binaryToBin(binaryString):
    return ''.join((shortIntToBin(binaryToShortInt(byte)) for byte in binaryString))


def binaryToShortInt(binaryString):
    return ord(binaryString)


def binaryToLongInt(binaryString):
    return long(binascii.b2a_hex(binaryString), 16)


##bin (text binary)

def binToBinary(binString):
    if not len(binString)%8 == 0:
        binString += (8 - len(binString)%8)*'0'
    return ''.join((shortIntToBinary(binToInt(binString[idx*8:idx*8+8])) for idx in xrange(0, len(binString)/8)))


def binToInt(binString):
    return int(binString,2)

    
def binToLongInt(binString):
    return long(binString,2)


def binToHex(binString):
    return hex(int(binString,2))


##short int

def shortIntToBinary(shortIntString):
    #1 Byte
    return chr(int(shortIntString))


def shortIntToBin(shortIntString):
    #1 Byte
    value = int(shortIntString)
    result = deque()
    exp = 7
    while exp >= 0:
        if 2 ** exp <= value:
            result.append('1')
            value -= 2 ** exp
        else:
            result.append('0')
        exp -= 1
    return ''.join(result)


##int

def intToBin(intString):
    return hexToBin(intToHex(long(intString)))


def intToLongInt(intString):
    return long(intString)


def intToHex(intString):
    return hex(int(long(intString)))


##long

def longIntToBinary(longString):
    number = long(longString)
    #4 Byte
    return (chr(number >> 24) + chr((number >> 16) & 0xFF) + 
            chr((number >> 8) & 0xFF) + chr(number & 0xFF))


#def longToBin(longString):
#    return hexToBin(longToHex(longString))


def longIntToBin(longString, bytes = 4):
    #Normal: 4 Byte
    value = long(longString)
    result = deque()
    exp = 8 * bytes - 1
    while exp >= 0:
        if 2 ** exp <= value:
            result.append('1')
            value -= 2 ** exp
        else:
            result.append('0')
        exp -= 1
    return ''.join(result)


def longIntToInt(longString):
    return int(long(longString))


def longIntToHex(longString):
    return hex(long(longString))


##hex

def hexToBin(hexString, length = None):
    hexToBinDict = {"0":"0000", "1":"0001", "2":"0010", "3":"0011",
                    "4":"0100", "5":"0101", "6":"0110", "7":"0111",
                    "8":"1000", "9":"1001", "A":"1010", "B":"1011",
                    "C":"1100", "D":"1101", "E":"1110", "F":"1111",
                    "-":"-"}
                
    if hexString[:2]=='0x':
        if hexString[-1:]=='L':
            hexString = hexString[2:-1]
        else:
            hexString = hexString[2:]
    else:
        if hexString[-1:]=='L':
            hexString = hexString[:-1]

    result = deque()
    for digit in hexString.upper():
        result.append(hexToBinDict[digit])
    result = ''.join(result)
    
    if length is not None:
        while length > len(result):
            result.appendleft('0')
    return result


def hexToInt(hexString):
    return int(long(hexString, 16))

    
def hexToLongInt(hexString):
    return long(hexString,16)


##hash

def hashToBin(toHash):
    return hexToBin(binascii.hexlify(sha.sha(toHash).digest()))


def hashToInt(toHash):
    return hexToInt(binascii.hexlify(sha.sha(toHash).digest()))


def hashToHex(toHash):
    return binascii.hexlify(sha.sha(toHash).digest()).upper()


##bt specific

def peerIdToClient(peerId):
    client = 'unknown'
                    
    if peerId[:3] == '-PB':
        client = 'PyBit ' + '.'.join([str(binaryToShortInt(byte)) for byte in peerId[3:6]])
        
        
    elif peerId[:3] == '-AZ':
        client = 'Azureus'
        
    elif peerId[2:4] == 'RS':
        client = 'I2PRufus ' + '.'.join([str(digit) for digit in (ord(peerId[0]), ord(peerId[1])/10, ord(peerId[1])%10)])
        
    elif peerId[2:4] == 'FU':
        client = 'Robert ' + '.'.join([str(digit) for digit in (ord(peerId[0]), ord(peerId[1])/10, ord(peerId[1])%10)])
        
    elif peerId[:9] == chr(0)*9:
        client = 'I2PSnark'
        
    elif peerId[:12] == chr(0)*12:
        client = 'I2P-Bt'
        
    return client        