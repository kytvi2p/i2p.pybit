"""
Copyright 2009  Blub

SamMessages, a collection of functions to parse and generate messages which are part of the SAM protocol.
This file is part of PySamLib.

PySamLib is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published
by the Free Software Foundation, version 2.1 of the License.

PySamLib is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with PySamLib.  If not, see <http://www.gnu.org/licenses/>.
"""

def parseMessage(data):
    message = {}
    data = data.split(' ')
    
    #get the message type
    message['msgType'] = ' '.join(data[:2])
    data = data[2:]
    
    #get the name=>value pairs
    parameters = {}
    for pair in data:
        pair = pair.split('=')
        parameters[pair[0].upper()] = '='.join(pair[1:])
    message['msgParas'] = parameters
    return message    

def sessionCreateMessage(type, destName, sessionDirection, sessionOptions):
    message = []
    message.append('SESSION CREATE STYLE=')
    if type=='tcp':
        message.append('STREAM')
    elif type=='udp':
        message.append('DATAGRAM')
    elif type=='raw':
        message.append('RAW')
    message.append(' DESTINATION=')
    message.append(destName)
    if type=='tcp':
        if sessionDirection=='both':
            message.append(' DIRECTION=BOTH')
        elif sessionDirection=='in':
            message.append(' DIRECTION=RECEIVE')
        elif sessionDirection=='out':
            message.append(' DIRECTION=CREATE')
    for option, value in sessionOptions.iteritems():
        message.append(' ')
        message.append(option)
        message.append('=')
        message.append(str(value))
    message.append('\n')
    return ''.join(message)

def datagramSendMessage(destination, data):    
    message = []
    message.append('DATAGRAM SEND DESTINATION=')
    message.append(destination)
    message.append(' SIZE=')
    message.append(str(len(data)))
    message.append('\n')
    message.append(data)
    return ''.join(message)

def streamConnectMessage(samId, destination):
    message = []
    message.append('STREAM CONNECT ID=')
    message.append(str(samId))
    message.append(' DESTINATION=')
    message.append(destination)
    message.append('\n')
    return ''.join(message)

def streamReceiveLimitMessage(samId, limit):
    message = []
    message.append('STREAM RECEIVE ID=')
    message.append(str(samId))
    message.append(' LIMIT=')
    message.append(str(limit))
    message.append('\n')
    return ''.join(message)

def streamSendMessage(samId, data):
    message = []
    message.append('STREAM SEND ID=')
    message.append(str(samId))
    message.append(' SIZE=')
    message.append(str(len(data)))
    message.append('\n')
    message.append(data)
    return ''.join(message)

def streamCloseMessage(samId):
    message = []
    message.append('STREAM CLOSE ID=')
    message.append(str(samId))
    message.append('\n')
    return ''.join(message)

def nameLookup(name):
    message = []
    message.append('NAMING LOOKUP NAME=')
    message.append(name)
    message.append('\n')
    return ''.join(message)