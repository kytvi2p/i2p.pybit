"""
Copyright 2009  Blub

HttpRequester, a general class for making requests to a http server; only implements
a very limited subset of the http specs.
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

import logging
import threading

from PySamLib.SamSocket import SamSocket
from Utilities import logTraceback

class HttpRequester:
    def __init__(self, eventScheduler, destNum, samSockManager, ownAddrFunc):
        self.sched = eventScheduler
        self.destNum = destNum
        self.samSockManager = samSockManager
        self.ownAddrFunc = ownAddrFunc
        
        self.requests = {}
        self.requestId = 0
        
        self.conns = {}
        self.allConns = set()
        self.connsWithSendInterest = set()
        self.connsWithRecvInterest = set()
        
        self.log = logging.getLogger('HttpRequester')
        self.lock = threading.RLock()
        
        #thread
        self.shouldStop = False
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
    
        
    ##internal functions - requests
        
    def _addRequest(self, addr, url, maxSize, callback, callbackArgs, callbackKws):
        self.log.debug('Adding request to "%s" for "%s" with maxSize "%d"', addr[:10], url, maxSize)
        self.requestId += 1
        
        #create conn
        sock = SamSocket(self.samSockManager, self.destNum)
        sock.setblocking(0)
        sock.connect(addr)
        sockNum = sock.fileno()
        
        #timeout
        timeoutEvent = self.sched.scheduleEvent(self.timeout, timedelta=300, funcArgs=[sockNum, 'transfer timeout'])
        
        #add to conn dict
        self.conns[sockNum] = {'sock':sock,
                               'connected':False,
                               'outBuffer':None,
                               'inBuffer':[],
                               'inBufferSize':0,
                               'neededBytes':None,
                               'timeout':timeoutEvent,
                               'requestId':self.requestId}
                               
        
        #add to sets
        self.allConns.add(sockNum)
        self.connsWithSendInterest.add(sockNum)
            
        #add to local requestDict
        self.requests[self.requestId] = {'url':url,
                                         'maxSize':maxSize,
                                         'callback':callback,
                                         'callbackArgs':callbackArgs,
                                         'callbackKws':callbackKws,
                                         'connId':sockNum}
                                        
    
    def _removeRequest(self, requestId):
        requestSet = self.requests[requestId]
        connId = requestSet['connId']
        connSet = self.conns[connId]
        
        #remove timeout
        self.sched.removeEvent(connSet['timeout'])
        
        #close conn, remove from sets
        connSet['sock'].close()
        self.allConns.remove(connId)
        self.connsWithSendInterest.discard(connId)
        self.connsWithRecvInterest.discard(connId)
        
        #remove conn from dict
        del self.conns[connId]
        
        #remove request
        del self.requests[requestId]
    
        
    def _reportRequestResult(self, requestSet, result):
        self.lock.release()
        try:
            apply(requestSet['callback'], [result]+requestSet['callbackArgs'], requestSet['callbackKws'])
        except:
            self.log.warn('Error while executing request callback:\n%s', logTraceback())
        self.lock.acquire()
        
        
    def _finishRequest(self, connSet):
        requestId = connSet['requestId']
        requestSet = self.requests[requestId]
        data = ''.join(connSet['inBuffer'])
        self.log.debug('Request to "%s" for "%s": finished successfully (response-length: %d)', connSet['sock'].getpeername()[:10], requestSet['url'], len(data))
        
        #remove request
        self._removeRequest(requestId)
        
        #call callback
        result = {'success':True,
                  'data':data}
        self._reportRequestResult(requestSet, result)
        
    
    def _failRequest(self, requestId, reason):
        requestSet = self.requests[requestId]
        connSet = self.conns[requestSet['connId']]
        self.log.debug('Request to "%s" for "%s": failed (reason: %s)', connSet['sock'].getpeername()[:10], requestSet['url'], reason)
        
        self._removeRequest(requestId)
        result = {'success':False,
                  'failureMsg':reason}
        self._reportRequestResult(requestSet, result)
        
        
    ##internal functions - http
    
    def _createHttpRequest(self, url):
        request = 'GET %s HTTP/1.1\r\nHost: %s\r\n\r\n' % (url, self.ownAddrFunc())
        return request
    
    
    def _parseHttpHeader(self, rawHeader):
        header = {}
        for headerLine in rawHeader:
            #one header line
            if ':' in headerLine:
                #chance that this is a valid header, process it
                headerLine = headerLine.split(':')
                key = headerLine[0].lower()
                value = ':'.join(headerLine[1:]).lstrip()
                if len(key) > 0 and len(value) > 0:
                    header[key] = value
        return header
    
    
    def _parseHttpResponse(self, response):
        success = False
        length = None
        
        response = response.split('\r\n')
        httpResponse = response[0].split(' ')
        header = self._parseHttpHeader(response[1:])
        if len(httpResponse)==3:
            #length is ok
            if httpResponse[0].lower() in ('http/1.0', 'http/1.1') and httpResponse[1] == '200' and httpResponse[2].lower() == 'ok':
                #response ok
                if 'content-length' in header:
                    try:
                        length = int(header['content-length'])
                        success = True
                    except:
                        pass
        return success, length
    
    
    ##internal functions - conns
    
    def _send(self, connId):
        connSet = self.conns[connId]
        requestSet = self.requests[connSet['requestId']]
        
        if not connSet['connected']:
            #connected, queue response
            self.log.debug('Request to "%s" for "%s": connected', connSet['sock'].getpeername()[:10], requestSet['url'])
            
            self.sched.rescheduleEvent(connSet['timeout'], timedelta=300)
            connSet['connected'] = True
            connSet['outBuffer'] = self._createHttpRequest(requestSet['url'])
            
        else:
            #already connected, send more data
            self.sched.rescheduleEvent(connSet['timeout'], timedelta=300)
            data = connSet['outBuffer']
            dataLen = len(data)
            sendBytes = connSet['sock'].send(data)
            
            self.log.debug('Request to "%s" for "%s": send %d bytes of request', connSet['sock'].getpeername()[:10], requestSet['url'], sendBytes)
            
            if sendBytes < dataLen:
                #not all send, requeue
                connSet['outBuffer'] = data[sendBytes:]
            
            else:
                #all send, wait for response
                self.log.debug('Request to "%s" for "%s": finished sending request, waiting for response', connSet['sock'].getpeername()[:10], requestSet['url'])
                connSet['outBuffer'] = None
                self.connsWithSendInterest.remove(connId)
                self.connsWithRecvInterest.add(connId)
                
                
    def _recv(self, connId):
        connSet = self.conns[connId]
        requestSet = self.requests[connSet['requestId']]
        self.sched.rescheduleEvent(connSet['timeout'], timedelta=300)
        
        #recv data
        data = connSet['sock'].recv()
        connSet['inBufferSize'] += len(data)
        
        data = ''.join(connSet['inBuffer']) + data
        connSet['inBuffer'] = [data]
        
        self.log.debug('Request to "%s" for "%s": got %d bytes of response', connSet['sock'].getpeername()[:10], requestSet['url'], len(data))
        
        if connSet['neededBytes'] is None and '\r\n\r\n' in data:
            #just finished http header
            self.log.debug('Request to "%s" for "%s": finished receiving header', connSet['sock'].getpeername()[:10], requestSet['url'])
        
            data = ''.join(connSet['inBuffer'])
            data = data.split('\r\n\r\n')
            httpHeader = data[0]
            data = '\r\n\r\n'.join(data[1:])
            
            #readd non-header data
            connSet['inBuffer'] = [data]
            connSet['inBufferSize'] = len(data)
            
            #examine http header
            valid, contentLength = self._parseHttpResponse(httpHeader)
            if not valid:
                #invalid header
                self._failRequest(connSet['requestId'], 'invalid response')
            else:
                #valid header
                if requestSet['maxSize'] < contentLength:
                    #response length over limit
                    self._failRequest(connSet['requestId'], 'response length over limit')
                else:
                    #ok
                    self.log.debug('Request to "%s" for "%s": header is valid (response-length: %d)', connSet['sock'].getpeername()[:10], requestSet['url'], contentLength)
                    connSet['neededBytes'] = contentLength
                
        if connSet['neededBytes'] is not None:
            #content length is known
            if connSet['neededBytes'] < connSet['inBufferSize']:
                #too much
                self._failRequest(connSet['requestId'], 'response length exceeds expected length')
                
            elif connSet['neededBytes'] == connSet['inBufferSize']:
                #finished
                self._finishRequest(connSet)
                
                
    ##internal functions - thread
    
    def _start(self):
        self.shouldStop = False
        if self.thread is None:            
            self.thread = threading.Thread(target=self.run)
            self.thread.start()
            
            
    def _stop(self):
        self.shouldStop = True
    
    
    ##internal function - main loop
    
    def run(self):
        try:
            self.lock.acquire()
            while not self.shouldStop:
                self.lock.release()
                recvable, sendable, errored = self.samSockManager.select(self.connsWithRecvInterest, self.connsWithSendInterest, self.allConns, timeout=1)
                self.lock.acquire()
                
                for connId in errored:
                    #conn failed, close it
                    if connId in self.allConns:
                        connSet = self.conns[connId]
                        if connSet['connected']:
                            self._failRequest(connSet['requestId'], 'connection failed')
                        else:
                            self._failRequest(connSet['requestId'], 'connect failed')
                    
                for connId in sendable:
                    if connId in self.allConns:
                        self._send(connId)
                        
                for connId in recvable:
                    if connId in self.allConns:
                        #received data
                        self._recv(connId)
                        
            self.thread = None
            self.log.info("Stopping")
            self.lock.release()
        except:
            self.log.error('Error in main loop:\n%s', logTraceback())
            
    
    ##internal functions - timeout
    
    def timeout(self, connId, reason):
        self.lock.acquire()
        if connId in self.conns:
            self._failRequest(self.conns[connId]['requestId'], reason)
        self.lock.release()
    
            
    ##external functions - requests
    
    def makeRequest(self, addr, url, callback, callbackArgs=[], callbackKws={}, maxSize=1048576):
        self.lock.acquire()
        requestId = self._addRequest(addr, url, maxSize, callback, callbackArgs, callbackKws)
        self.lock.release()
        return requestId
    
    
    def abortRequest(self, requestId):
        self.lock.acquire()
        if requestId in self.requests:
            self._removeRequest(requestId)
        self.lock.release()
        
        
    ##external functions - other
    
    def start(self):
        self.lock.acquire()
        self._start()
        self.lock.release()
        
        
    def stop(self):
        self.lock.acquire()
        thread = self.thread
        self._stop()
        self.lock.release()
        if thread is not None:
            thread.join()
        
        
if __name__=="__main__":
    from EventScheduler import EventScheduler
    from PySamLib.SamSocketManager import SamSocketManager
    
    
    #configure logging module
    logging.basicConfig(level=logging.DEBUG,
                        filename="httplog",
                        format='%(asctime)s %(levelname)-8s %(name)-14s - %(message)s')
    
    #samSockManager
    samSockManager = SamSocketManager(log='SamSocketManager', asmLog='AsyncSocketManager')
    destNum = samSockManager.addDestination('127.0.0.1', 7656, 'Test', 'tcp', 'both')
    
    #event scheduler
    eventSched = EventScheduler()
    
    #funcs
    def addrFunc():
        return '127.0.0.1'
    
    def callb(result, requester, eventSched, sockManag, destNum):
        print 'Result:', result
        requester.stop()
        eventSched.stop()
        sockManag.removeDestination(destNum)
        
    #destination
    addr = 'YQERBdlelBfPITVkEM248HCPiDrZB4DrxU1mH8zsI1WECYWIXp5CMDWH3aQLnpqKpEs6LRi~z7OScK-G0KcKaQlTMb1q0qle5OdwmrEHbq6Q3eHH493UHvI-iu~ZPa8a4j6xXqXO~400IRgWCEInKk6GPXxhZrYsD6lA-rT-H7M1XhGwmIL6P-sIOk4TO-HzoDG~2Gd~4zWm6-zmuXnbHqdiSEnqPIOL53FKovsMsSkxQiDyA0tK-YEQEVsMPW2Qokt-Ds-TmmPsra88X5oky6zQH1Nz9OFaMl3swvcVAq2qwrfF-bgl~Sbph2UXrfI~vnmDsD~hpMwv9tk97rjJVZluf8S3WO7-IToO0gHv3t1xJHpZViknBVgdxGdTlObLHew3JKCovQe3GYdlEGH~yRQ0IZiopbNqPh-m-RdKXpupaedcqveRnBpNXPNADRsDILP8Bsnry9RO7SdVxJx12ll~vfDmbNfSrllcOyA6AFStpGdNrxQR40QqME1AzNd3AAAA'
    url = '/gcache.py?urlfile=1'
    
    requester = HttpRequester(eventSched, destNum, samSockManager, addrFunc)
    requester.makeRequest(addr, url, callb, callbackArgs=[requester, eventSched, samSockManager, destNum])
