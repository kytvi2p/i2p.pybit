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

from __future__ import with_statement
from sha import sha
import logging
import os
import threading

from Status import Status
from Utilities import logTraceback


class StorageException(Exception):
    pass


class Storage:
    def __init__(self, ident, torrent, pathprefix):
        self.torrent = torrent
        self.pathprefix = pathprefix
        
        #loading
        self.loaded = False
        self.shouldAbortLoad = False
        self.loadLock = threading.Lock()
        
        #other
        self.ownStatus = Status(self.torrent.getTotalAmountOfPieces())
        self.log = logging.getLogger(ident+'-Storage')
        self.lock = threading.Lock()
        
        
    ##internal functions - files
    
    def _getFilePath(self, filePath):
        realFilePath = os.path.normpath(os.path.join(self.pathprefix, filePath))
        if not realFilePath.startswith(self.pathprefix):
            raise StorageException('Security violation: file "%s" is not inside base directory "%s" (original path: "%s")' % (realFilePath, self.pathprefix, os.path.join(self.pathprefix, filePath)))
        return realFilePath
    
        
    ##internal functions - loading
        
    def _checkFile(self, binaryNull, filePath, wantedFileSize):
        #checks path to file and the size of the file itself,
        #may throw StorageException if the file path is not acceptable or a directory or file operation fails
        
        #get file path
        realFilePath = self._getFilePath(filePath)
        
        #check directory
        dirPath = os.path.dirname(realFilePath)
        if not os.path.exists(dirPath):
            #directory doesn't exist, create it
            self.log.debug('Creating Directory "%s"', dirPath)
            try:
                os.makedirs(dirPath)
            except OSError:
                raise StorageException('Failed to create directory "%s":\n%s' % (dirPath, logTraceback()))
        
        #check file
        try:
            fl = open(realFilePath, 'ab')
            with fl:
                #file opened
                fl.seek(0, 2)
                currentFileSize = fl.tell()
                if currentFileSize < wantedFileSize:
                    self.log.debug('File "%s" is %d bytes to short', realFilePath, wantedFileSize - currentFileSize)
                else:
                    self.log.debug('File "%s" has the correct size', realFilePath)
                
                #fill if needed            
                while (not self.shouldAbortLoad) and currentFileSize + 1048576 < wantedFileSize:
                    fl.write(binaryNull)
                    currentFileSize += 1048576
                
                if not self.shouldAbortLoad:
                    #write remaining bytes
                    fl.write(chr(0)*(wantedFileSize - currentFileSize))
            
        except IOError:
            #something failed
            raise StorageException('Failure while processing file "%s":\n%s' % (realFilePath, logTraceback()))
            
            
    def _checkPieceAvailability(self):
        #check which pieces are already finished
        #may throw StorageException if things go wrong
        piece = 0
        pieceAmount = self.torrent.getTotalAmountOfPieces()
        while (not self.shouldAbortLoad) and piece < pieceAmount:
            #check piece
            data = self.getData(piece, 0, self.torrent.getLengthOfPiece(piece))
            if sha(data).digest() == self.torrent.getPieceHashByPieceIndex(piece):
                #hash matches, piece is finished
                self.ownStatus.setPieceStatus(piece, True)
                self.log.debug('Piece Nr. %d is finished', piece)
            else:
                #hash doesn't match, not finished
                self.ownStatus.setPieceStatus(piece, False)
                self.log.debug('Piece Nr. %d is  not finished', piece)
            piece += 1
    
    
    ##external functions - loading - need self.loadLock
    
    def load(self):
        with self.loadLock:
            #inside lock
            self.log.info('Loading files of torrent')
            
            #check files of torrent
            files = self.torrent.getFiles()
            binaryNull = chr(0)*1048576 #one megabyte
            place = 0
            while (not self.shouldAbortLoad) and place < len(files):
                fileSet = files[place]
                self._checkFile(binaryNull, fileSet['path'], fileSet['size'])
                place += 1
            
            #check which pieces are already finished
            self._checkPieceAvailability()
            
            if not self.shouldAbortLoad:
                #loading finished
                self.loaded = True
            
    
    def abortLoad(self):
        #abort loading
        self.shouldAbortLoad = True
        with self.loadLock:
            self.shouldAbortLoad = False
        
    
    def isLoaded(self):
        return self.loaded
    
    
    ##external functions - pieces - need self.lock (to prevent parallel access to the same file)
    
    def getData(self, pieceIndex, addOffset, length):
        with self.lock:
            #inside lock, get responsible files
            fromOffset = self.torrent.convertPieceIndexToOffset(pieceIndex, addOffset)
            files = self.torrent.getFilesForOffset(fromOffset, fromOffset + length)
            
            #read data from files
            data = []
            for sfile in files:
                filePath = self._getFilePath(sfile['path'])
                
                try:
                    #read data from file
                    datafile = open(filePath, 'rb')
                    with datafile:
                        #file opened
                        datafile.seek(sfile['offset'])
                        fileData = datafile.read(sfile['bytes'])
                    
                except IOError:
                    #file operation failed
                    raise StorageException('Failure while trying to read from file "%s":\n%s' % (filePath, logTraceback()))
                    
                if len(fileData) == sfile['bytes']:
                    #got enough data
                    data.append(fileData)
                else:
                    #too few bytes, something went wrong here - too short file?!
                    raise StorageException('Couldn\'t read enough bytes from file "%s": wanted %i, got %i' % (sfile['path'], sfile['bytes'], len(fileData)))
                
            data = ''.join(data)
        return data


    def getDataHandle(self, pieceIndex, addOffset, length):
        def handle(self=self, pieceIndex=pieceIndex, addOffset=addOffset, length=length):
            return self.getData(pieceIndex, addOffset, length)
        return handle


    def storeData(self, pieceIndex, data, offset=0):
        with self.lock:
            #inside lock, get responsible files
            fromOffset = self.torrent.convertPieceIndexToOffset(pieceIndex) + offset
            files = self.torrent.getFilesForOffset(fromOffset, fromOffset+len(data))
            
            #store data
            for sfile in files:
                filePath = self._getFilePath(sfile['path'])
                
                try:
                    datafile = open(filePath, 'rb+')
                    with datafile:
                        datafile.seek(sfile['offset'])
                        datafile.write(data[:sfile['bytes']])
                        data = data[sfile['bytes']:]
                        
                except IOError:
                    #file operation failed
                    raise StorageException('Failure while trying to write to file "%s":\n%s' % (filePath, logTraceback()))


    ##external functions - stats

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
        totalBytes = self.torrent.getTotalSize()
        gotBytes = self.getAmountOfGotBytes()
        
        stats['progressBytes'] = gotBytes
        stats['progressPercent'] = 100 * gotBytes / (totalBytes * 1.0)
        return stats