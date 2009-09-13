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

##builtin
from __future__ import with_statement
from sha import sha
from time import time
import logging
import os
import threading

##own
from Status import PersistentStatus
from Utilities import logTraceback


class StorageException(Exception):
    def __init__(self, reason, *args):
        self.reason = reason % args
        Exception.__init__(self, self.reason)
        
        
        

class Storage:
    def __init__(self, config, btPersister, ident, torrent, pathprefix):
        self.config = config
        self.btPersister = btPersister
        self.torrent = torrent
        self.pathprefix = pathprefix
        
        #loading
        self.loaded = False
        self.shouldAbortLoad = False
        self.loadLock = threading.Lock()
        
        #other
        shouldPersist = self.config.get('storage', 'persistPieceStatus')
        self.ownStatus = PersistentStatus(btPersister, shouldPersist, self.torrent.getTotalAmountOfPieces())
        self.log = logging.getLogger(ident+'-Storage')
        self.lock = threading.Lock()
        
        
    ##internal functions - files
    
    def _getFilePath(self, filePath):
        realFilePath = os.path.normpath(os.path.join(self.pathprefix, filePath))
        if not realFilePath.startswith(self.pathprefix):
            raise StorageException('Security violation: file "%s" is not inside base directory "%s" (original path: "%s")', realFilePath, self.pathprefix, os.path.join(self.pathprefix, filePath))
        return realFilePath
    
        
    ##internal functions - loading
        
    def _checkFile(self, filePath, wantedFileSize):
        #checks path to file and the size of the file itself,
        #may throw StorageException if the file path is not acceptable or a directory or file operation fails
        created = False
        modified = False
        
        #get file path
        realFilePath = self._getFilePath(filePath)
        
        #check directory
        dirPath = os.path.dirname(realFilePath)
        if not os.path.exists(dirPath):
            #directory doesn't exist, create it
            created = True
            self.log.debug('Creating Directory "%s"', dirPath)
            try:
                os.makedirs(dirPath)
            except OSError:
                raise StorageException('Failed to create directory "%s":\n%s' % (dirPath, logTraceback()))
        
        
        #check file
        if not os.path.exists(realFilePath):
            #file needs to be created
            fl = open(realFilePath, 'ab')
            fl.close()
            created = True
        
        self.log.debug('Processing file "%s" (original name "%s"): new "%s", isdir "%s", isfile "%s", islink "%s", dirname "%s", basename "%s"',\
                       realFilePath, filePath, str(created), str(os.path.isdir(realFilePath)), str(os.path.isfile(realFilePath)),\
                       str(os.path.islink(realFilePath)), dirPath, os.path.basename(realFilePath))
        try:
            fl = open(realFilePath, 'rb+')
            with fl:
                #file opened
                fl.seek(0, 2)
                currentFileSize = fl.tell()
                if currentFileSize < wantedFileSize:
                    self.log.debug('File "%s" is %d bytes to short', realFilePath, wantedFileSize - currentFileSize)
                    modified = True
                else:
                    self.log.debug('File "%s" has the correct size', realFilePath)
                
                #fill if needed
                if (not self.shouldAbortLoad) and currentFileSize + 1045876 < wantedFileSize:
                    #large fill
                    start = time()
                    fl.seek(1048575, 1)
                    fl.write('\x00')
                    fl.flush()
                    currentFileSize = fl.tell()
                    needed = time() - start
                    
                    try:
                        step = int(1048575 * 0.1 / needed)
                    except ZeroDivisionError:
                        step = wantedFileSize - currentFileSize - 1
                    step = max(1, step)
                    self.log.debug('Needed %f seconds for 1 Mb, step size %i', needed, step)
                    
                    while (not self.shouldAbortLoad) and currentFileSize + step <= wantedFileSize - 1:
                        fl.seek(step, 1)
                        fl.write('\x00')
                        fl.flush()
                        currentFileSize = fl.tell()
                        self.log.debug("Progress: %i / %i", currentFileSize, wantedFileSize)
                
                if (not self.shouldAbortLoad) and currentFileSize < wantedFileSize: 
                    #seek remaining bytes and write last byte
                    fl.seek((wantedFileSize - currentFileSize - 1), 1)
                    fl.write('\x00')
                    fl.flush()
                    currentFileSize = fl.tell()
                    self.log.debug("Progress: %i / %i", currentFileSize, wantedFileSize)
            
        except IOError:
            #something failed
            raise StorageException('Failure while processing file "%s":\n%s' % (realFilePath, logTraceback()))
        
        return created, modified
        
        
    def _checkAllFiles(self):
        anyModified = False
        allCreated = True
        
        files = self.torrent.getFiles()
        place = 0
        while (not self.shouldAbortLoad) and place < len(files):
            fileSet = files[place]
            created, modified = self._checkFile(fileSet['path'], fileSet['size'])
            anyModified |= modified
            allCreated &= created
            place += 1
        return allCreated, anyModified
            
            
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
            
            
    def _load(self, completionCallback):
        with self.loadLock:
            #inside lock
            self.log.info('Loading files of torrent')
            loadSuccess = False
            
            try:
                #check files of torrent
                if not self.config.get('storage', 'skipFileCheck'):
                    #skipping is not allowed
                    self.log.debug('Not allowed to skip file checking, starting check')
                    allCreated, anyModified = self._checkAllFiles()
                    self.btPersister.store('Storage-checkedFiles', True)
                
                elif not self.btPersister.get('Storage-checkedFiles', False):
                    #skipping would be allowed but we didn't check even once up to now
                    self.log.debug('Files were not checked up to now, starting check')
                    allCreated, anyModified = self._checkAllFiles()
                    self.btPersister.store('Storage-checkedFiles', True)
                    
                else:
                    #skipping is allowed and files were already checked
                    self.log.debug('Skipping file checking')
                    allCreated = False
                    anyModified = False
                
                
                #check which pieces are already finished
                if allCreated:
                    #no need to check piece availability, all files were just written to disk
                    self.log.debug('Skipping hashing, files were just created')
                    
                else:
                    #possibly need to check, some files already existed
                    if self.ownStatus.loadPersistedData():
                        #persisted status info existed
                        self.log.debug('Skipping hashing, managed to load persisted status data')
                    else:
                        #there is no persisted data
                        self.log.debug('Checking which pieces are already finished')
                        self._checkPieceAvailability()
                    
                    
                #check if loading wasn't aborted
                if not self.shouldAbortLoad:
                    self.ownStatus.persist()
                    loadSuccess = True
                    self.loaded = True
                    
            except StorageException, se:
                self.log.error('Failure during load:\n%s', logTraceback())
            
            if not self.shouldAbortLoad:
                completionCallback(loadSuccess)
    
    
    ##external functions - loading - need self.loadLock
    
    def load(self, completionCallback):
        thread = threading.Thread(target=self._load, args=(completionCallback,))
        thread.start()
        
    
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
                
                
    ##external functions - stats - no locking

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
        #no locking, status class already contains locking
        return self.ownStatus
    
    
    def getStats(self):
        #not locked, nothing needs that
        stats = {}
        totalBytes = self.torrent.getTotalSize()
        gotBytes = self.getAmountOfGotBytes()
        
        stats['progressBytes'] = gotBytes
        stats['progressPercent'] = 100 * gotBytes / (totalBytes * 1.0)
        return stats