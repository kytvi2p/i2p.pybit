"""
Copyright 2009  Blub

Storage, the class which is responsible of receiving and saving data from/to the data files of a torrent job.
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

from sha import sha
import logging
import os
import threading

from Status import Status

class Storage:
    def __init__(self, ident, torrent, pathprefix):
        self.torrent = torrent
        self.pathprefix = pathprefix
        
        self.loaded = False
        self.shouldAbortLoad = False
        
        self.ownStatus = Status(self.torrent.getTotalAmountOfPieces())
        self.log = logging.getLogger(ident+'-Storage')
        self.lock = threading.RLock()
        
        
    def _createFile(self, pathname):
        pathname = pathname.split('/')
        directories = pathname[:-1]
        place = 0
        while place < len(directories):     
            path = '/'.join(directories[0:place+1])
            try:
                self.log.debug('Creating Directory "%s"', path)
                os.mkdir(path)                
            except:
                self.log.debug('Directory "%s" already exists', path)
            place += 1
        filed = open('/'.join(pathname), 'wb')
        filed.close()
        
        
    def _getFilePath(self, pathprefix, filePath):
        combinedPath = os.path.normpath(os.path.join(pathprefix, filePath))
        if not combinedPath.startswith(pathprefix):
            raise Exception('Security violation: file "%s" is not inside base directory "%s" (original path: "%s")' % (combinedPath, pathprefix, os.path.join(pathprefix, filePath)))
        return combinedPath
        
        
    def load(self):
        self.lock.acquire()
        self.log.info('Loading Torrentfiles')
        #check for files
        files = self.torrent.getFiles()
        
        binaryNull = chr(0)*1048576 #one megabyte
        place = 0
        while (not self.shouldAbortLoad) and place < len(files):
            fl = files[place]
            
            #create file if necessary
            flPath = self._getFilePath(self.pathprefix, fl['path'])
            try:
                filed = open(flPath, 'rb')
                filed.close()
                self.log.debug('File "%s" exists', flPath)
            except:
                self._createFile(flPath)
            
            #adjust size of file
            filed = open(flPath, 'ab')
            filed.seek(0, 2)
            size = filed.tell()
            if size < fl['size']:
                self.log.debug('File "%s" is %d bytes to short', flPath, fl['size'] - size)
            else:
                self.log.debug('File "%s" has the correct size', flPath)
            
            #fill if needed            
            while (not self.shouldAbortLoad) and size + 1048576 < fl['size']:
                filed.write(binaryNull)
                size += 1048576
            
            if not self.shouldAbortLoad:
                #write remaining bytes
                filed.write(chr(0)*(fl['size'] - size))
            filed.close()
            
            place += 1
            
        
        #check which pieces are already finished
        piece = 0
        pieceAmount = self.torrent.getTotalAmountOfPieces()
        while (not self.shouldAbortLoad) and piece < pieceAmount:
            data = self.getData(piece, 0, self.torrent.getLengthOfPiece(piece))
            if sha(data).digest()==self.torrent.getPieceHashByPieceIndex(piece):
                self.ownStatus.gotPiece(piece)
                self.log.debug('Piece Nr. %d is finished', piece)
            else:
                self.log.debug('Piece Nr. %d is  not finished', piece)
            piece += 1
        
        if self.shouldAbortLoad:
            self.ownStatus.clear()
        else:
            self.loaded = True
        self.lock.release()
    
    def abortLoad(self):
        self.shouldAbortLoad = True
        self.lock.acquire()
        self.shouldAbortLoad = False
        self.lock.release()
    
    def isLoaded(self):
        self.lock.acquire()
        loaded = self.loaded
        self.lock.release()
        return loaded
    
    
    def getData(self, pieceIndex, addOffset, length):
        self.lock.acquire()
        fromOffset = self.torrent.convertPieceIndexToOffset(pieceIndex, addOffset)
        files = self.torrent.getFilesForOffset(fromOffset, fromOffset + length)
        data = []
        for sfile in files:
            filePath = self._getFilePath(self.pathprefix, sfile['path'])
            datafile = open(filePath, 'rb')
            datafile.seek(sfile['offset'])
            data.append(datafile.read(sfile['bytes']))
            datafile.close()
        data = ''.join(data)
        self.lock.release()
        return data


    def getDataHandle(self, pieceIndex, addOffset, length):
        def handle(self=self, pieceIndex=pieceIndex, addOffset=addOffset, length=length):
            return self.getData(pieceIndex, addOffset, length)
        return handle


    def storeData(self, pieceIndex, data, offset=0):
        self.lock.acquire()
        fromOffset = self.torrent.convertPieceIndexToOffset(pieceIndex) + offset
        files = self.torrent.getFilesForOffset(fromOffset, fromOffset+len(data))
        for sfile in files:
            filePath = self._getFilePath(self.pathprefix, sfile['path'])
            datafile = open(filePath, 'rb+')
            datafile.seek(sfile['offset'])
            datafile.write(data[:sfile['bytes']])
            data = data[sfile['bytes']:]
            datafile.close()
        self.lock.release()


    def getAmountOfMissingBytes(self):
        #not locked, nothing needs that
        missingBytes = self.ownStatus.getAmountOfMissingPieces()*self.torrent.getPieceLength()
        lastPieceIndex = self.torrent.getTotalAmountOfPieces()-1
        if not self.ownStatus.hasPiece(lastPieceIndex):
            missingBytes -= (self.torrent.getPieceLength() - self.torrent.getLengthOfPiece(lastPieceIndex))
        return missingBytes
    
    
    def getAmountOfGotBytes(self):
        #not locked, nothing needs that
        gotBytes = self.ownStatus.getAmountOfGotPieces() * self.torrent.getPieceLength()
        lastPieceIndex = self.torrent.getTotalAmountOfPieces()-1
        if self.ownStatus.hasPiece(lastPieceIndex):
            gotBytes -= (self.torrent.getPieceLength() - self.torrent.getLengthOfPiece(lastPieceIndex))
        return gotBytes


    def getStatus(self):
        return self.ownStatus
    
    
    def getStats(self):
        #not locked, nothing needs that
        stats = {}
        totalBytes= self.torrent.getTotalSize()
        gotBytes = self.getAmountOfGotBytes()
        
        stats['progressBytes'] = gotBytes
        stats['progressPercent'] = 100 * gotBytes / (totalBytes * 1.0)
        return stats