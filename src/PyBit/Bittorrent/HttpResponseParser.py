"""
Copyright 2009  Blub

HttpResponseParser, a class for parsing http responses of http 1.1
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
import logging

from Conversion import hexToInt
from HttpUtilities import joinRelativeUrl


class HttpResponseParserException(Exception):
    def __init__(self, reason, *args):
        self.reason = reason % args
        Exception.__init__(self, self.reason)
        
    def getReason(self):
        return self.reason
        

class HttpResponseParser:
    def __init__(self, addr, host, url, maxHeaderSize=1024, maxDataSize=1048576):
        self.addr = addr
        self.host = host
        self.url = url
        self.userHeaderSizeLimit = maxHeaderSize
        self.userDataSizeLimit = maxDataSize
        
        #data
        self.header = None
        self.data = None
        self.dataSize = 0
        self.maxDataSize = 0
        
        #state
        self.step = 'header'
        self.newline = None
        self.transferEncoding = None
        self.finished = False
        
        #buffers
        self.buffer = deque()
        self.bufferSize = 0
        self.maxBufferSize = self.userHeaderSizeLimit
        
        #log
        self.log = logging.getLogger('HttpResponseParser')
        
    
    ##internal functions - request
    
    def _createHttpRequest(self):
        if type(self.host) == str:
            host = self.host
        else:
            host = self.host.encode('UTF-8', 'ignore')
            
        request = '\r\n'.join(('GET %s HTTP/1.1' % (joinRelativeUrl(self.url),),
                               'Host: %s' % (host,),
                               'Accept-Encoding: identity',
                               '\r\n'))
        return request
        
    
    ##internal functions - buffer
    
    def _setMaxBufferSize(self, bytes):
        self.log.debug('Setting max buffer size to "%i" bytes', bytes)
        self.maxBufferSize = bytes
    
    def _getAllChunks(self, clear=True):
        data = ''.join(self.buffer)
        self.buffer.clear()
        self.bufferSize = 0
        return data
    
        
    def _getLastChunk(self):
        if len(self.buffer) == 0:
            lastChunk = ''
        else:
            lastChunk = self.buffer.pop()
            self.bufferSize -= len(lastChunk)
        return lastChunk
    
    
    def _storeChunk(self, data):
        #store data in buffer
        self.buffer.append(data)
        self.bufferSize += len(data)
        
        #check size
        if self.bufferSize > self.maxBufferSize:
            raise HttpResponseParserException('buffer size exceeds limit while receiving "%s"', self.step)
      
    
    def _clearBuffer(self):
        self.buffer.clear()
        self.bufferSize = 0
        
        
    ##internal functions - data buffer
    
    def _increaseDataSizeLimit(self, additionalBytes):
        if self.maxDataSize + additionalBytes > self.userDataSizeLimit:
            raise HttpResponseParserException('data size exceeds limit while receiving "%s"', self.step)
        else:
            self.maxDataSize += additionalBytes
            self.log.debug('Increasing max data size by "%i" bytes to "%i" bytes', additionalBytes, self.maxDataSize)
            
    
    def _storeData(self, data):
        #store data
        self.data.append(data)
        self.dataSize += len(data)
        
        if self.dataSize > self.maxDataSize:
            raise HttpResponseParserException('data size exceeds exptected size while receiving "%s"', self.step)
        
    
    def _getData(self):
        return ''.join(self.data)
    
        
    ##internal functions - header
    
    def _parseHeaderValues(self, rawHeader, headerName='header'):
        headerValues = {}
        
        #first merge everything
        place = 0
        while place < len(rawHeader):
            headerLine = rawHeader[place]
            if ':' in headerLine:
                #go on
                place += 1
            else:
                #merge
                if place == 0:
                    raise HttpResponseParserException('First key:value line in %s is invalid: "%s"', headerName, headerLine)
                else:
                    rawHeader[place-1] += headerLine.lstrip()
                    del rawHeader[place]
                    
        #now parse it
        for headerLine in rawHeader:
            #one header line
            headerLine = headerLine.split(':')
            key = headerLine[0].lower()
            value = ':'.join(headerLine[1:]).lstrip()
            if ',' in value:
                #multiple values
                value = list([part.strip() for part in value.split(',') if not part.strip() == ''])
                if len(value) == 0:
                    value = ''
                
            if len(key) == 0:
                raise HttpResponseParserException('Invalid key:value line in %s, key is empty: "%s"', headerName, headerline)
            else:
                headerValues[key] = value

        return headerValues
        
    
    def _parseHeader(self, header):
        header = header.split(self.newline)
        headerStatus = [part for part in header[0].split(' ') if not part == '']
        headerValues = self._parseHeaderValues(header[1:])
        
        #check for invalid status lines
        if not len(headerStatus) == 3:
            raise HttpResponseParserException('Invalid header status line: "%s"', header[0])
        
        if not headerStatus[0].lower() in ('http/1.0', 'http/1.1'):
            raise HttpResponseParserException('Unsupported http version: "%s"', headerStatus[0])
        
        #check type of response
        if headerStatus[1] == '100':
            #continue
            self.log.info('Got intermediary response from server: "%s %s"', headerStatus[1], headerStatus[2])
            
        elif not headerStatus[1] == '200':
            #failure
            self.header = {'code':headerStatus[1],
                           'codeText':headerStatus[2],
                           'values':headerValues}
            raise HttpResponseParserException('Request failed, got response "%s %s"', headerStatus[1], headerStatus[2])
        
        else:
            #200 = success
            self.header = {'code':headerStatus[1],
                           'codeText':headerStatus[2],
                           'values':headerValues}
            
            if 'transfer-encoding' in headerValues and not headerValues.get('transfer-encoding', 'none') == 'identity':
                if not headerValues['transfer-encoding'] == 'chunked':
                    #unsupported transfer encoding
                    raise HttpResponseParserException('Unsupported transfer encoding: "%s"', headerValues['transferEncoding'])
                else:
                    #chunked encoding
                    self.step = 'chunk header'
                    self.data = deque()
                    self.transferEncoding = 'chunked'
                    
                    self.log.debug('Got response "%s %s" from server: detected chunked transfer encoding', headerStatus[1], headerStatus[2])
                    
            elif 'content-length' in headerValues:
                #no transfer encoding
                try:
                    length = int(headerValues['content-length'])
                except ValueError:
                    raise HttpResponseParserException('Invalid value in "content-length" field: "%s"', headerValues['content-length'])
                
                self.log.debug('Got response "%s %s" from server: detected plain transfer type, expecting "%i" bytes', headerStatus[1], headerStatus[2], length)
                
                #adapt state
                self.step = 'body'
                self.data = deque()
                self.transferEncoding = None
                self._increaseDataSizeLimit(length)
                    
            else:
                #unsupported type of transfer
                raise HttpResponseParserException('Malformed or unsupported http header: "%s"', self.newline.join(header))
    
    
    def _processHeaderData(self, data):
        data = self._getLastChunk() + data
                
        #try to find the endline of the header
        if '\n\n' in data:
            self.newline = '\n'
        elif '\r\n\r\n' in data:
            self.newline = '\r\n'
            
        if self.newline is None:
            #still not finished
            self.log.debug('Got "%i" bytes of header', len(data))
            self._storeChunk(data)
            data = ''
            
        else:
            #found end of header, split data up
            data = data.split(self.newline*2)
            self._storeChunk(data[0])
            data = (self.newline*2).join(data[1:])
            
            #parse header
            self._parseHeader(self._getAllChunks())
            
        return data
    
    
    ##internal functions - body
    
    def _processBodyData(self, data):
        self.log.debug('Got "%i" bytes of data', len(data))
        self._storeData(data)
        if self.dataSize == self.maxDataSize:
            self.finished = True
        return ''
    
    
    ##internal functions - chunks
    
    def _processChunkHeaderData(self, data):
        data = self._getLastChunk() + data
        
        if not self.newline in data:
            #line is not finished
            self.log.debug('Got "%i" bytes of chunk header', len(data))
            self._storeChunk(data)
            data = ''
        
        else:
            #finished chunk header
            data = data.split(self.newline)
            self._storeChunk(data[0])
            data = self.newline.join(data[1:])
            
            #decode chunk length
            chunkHeader = self._getAllChunks()
            if ';' in chunkHeader:
                #remove chunk extensions
                chunkHeader = chunkHeader.split(';')[0]
            
            try:
                length = hexToInt(chunkHeader)
            except ValueError:
                raise HttpResponseParserException('Invalid chunk length "%s"', chunkHeader)
            
            if length == 0:
                #got all data
                self.log.debug('Got final chunk header, waiting for trailer')
                self.step = 'trailer'
                
            else:
                #next chunk
                self.log.debug('Got chunk header, expecting chunk body with "%i" bytes', length)
                self.step = 'chunk body'
                self._increaseDataSizeLimit(length)
                self._setMaxBufferSize(length)
        return data
    
    
    def _processChunkBodyData(self, data):
        neededBytes = self.maxBufferSize - self.bufferSize
        newlineLength = len(self.newline)
        
        if len(data) < neededBytes + newlineLength:
            #only a part of the data
            self.log.debug('Received "%i" bytes of chunk body', len(data))
            self._storeChunk(data)
            data = ''
        else:
            #got enough data
            self._storeChunk(data[:neededBytes])
            if not data[neededBytes:neededBytes+newlineLength] == self.newline:
                #chunk is too long
                raise HttpResponseParserException('Received data exceeds expected chunk size')
            else:
                #all ok
                self._storeData(self._getAllChunks())
                self._setMaxBufferSize(self.userHeaderSizeLimit)
                self.log.debug('Completed chunk body, waiting for next chunk header')
                data = data[neededBytes+newlineLength:]
                self.step = 'chunk header'
                
        return data
    
    
    ##internal functions - trailer
    
    def _processTrailerData(self, data):
        data = self._getLastChunk() + data
        if self.bufferSize == 0 and data == self.newline:
            #there is no trailing data at all
            data = self.newline*2
            
        if not self.newline*2 in data:
            #still not finished
            self._storeChunk(data)
            data = ''
            
        else:
            #found end of trailer, split data up
            data = data.split(self.newline*2)
            self._storeChunk(data[0])
            data = (self.newline*2).join(data[1:])
            
            if not data == '':
                raise HttpResponseParserException('Received trailing data after end of response')
            else:
                #parse trailer
                self.log.debug('Got trailer')
                trailerValues = self._parseHeaderValues(self._getAllChunks(), 'trailer')
                headerValues = self.header['values']
                for key, value in trailerValues:
                    if key in headerValues:
                        raise HttpResponseParserException('Received key "%s" both in the header and in the trailer', key)
                    else:
                        headerValues[key] = value
                        
                self.finished = True
        return data
    
    
    ##external functions
    
    def getHttpRequest(self):
        return self._createHttpRequest()
    
        
    def handleData(self, data):
        while len(data) > 0:
            #go on until no data is left or a failure occured
            if self.step == 'header':
                #still need header
                data = self._processHeaderData(data)
                
            elif self.step == 'body':
                #plain data
                data = self._processBodyData(data)
                
            elif self.step == 'chunk header':
                #chunk header
                data = self._processChunkHeaderData(data)
                
            elif self.step == 'chunk body':
                #chunk body
                data = self._processChunkBodyData(data)
                
            elif self.step == 'trailer':
                #trailer
                data = self._processTrailerData(data)
                
        return self.finished
    
    
    def getData(self):
        return self._getData()