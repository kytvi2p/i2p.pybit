"""
Copyright 2009  Blub

TorrentCreator, a class which can create new torrents.
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
from collections import deque
from sha import sha
import os
import threading

##own
from Bencoding import bencode
from Utilities import logTraceback


class TorrentCreatorException(Exception):
    def __init__(self, reason, *args):
        self.traceback = logTraceback()
        self.reason = reason % args
        Exception.__init__(self, self.reason)
        

class TorrentCreator:
    def __init__(self):
        #status
        self.thread = None
        self.shouldAbort = False
        self.running = False
        self.lastError = None
        
        self.amountOfFiles = 0
        self.currentFileNumber = 0
        self.currentFileName = ''
        self.currentFileProgress = 0.0
        self.totalFileSize = 0
        self.processedFileSize = 0
        
        
    def _getFiles(self, basePath):
        try:
            self.amountOfFiles = 0
            self.totalFileSize = 0
            
            if not os.path.exists(basePath):
                #doesn't exist
                raise TorrentCreatorException('Path "%s" doesn\'t exist!', basePath)
            
            elif not os.path.isdir(basePath):
                #not a directory
                realBasePath = os.path.realpath(basePath)
                try:
                    with open(realBasePath, 'rb') as fl:
                        fl.seek(0,2)
                        size = fl.tell()
                except IOError:
                    raise TorrentCreatorException('Failed to access file "%s" (absolute path "%s")!', basePath, realBasePath)
                files = [(tuple((os.path.basename(basePath),)), realBasePath, size)]
                self.amountOfFiles = 1
                self.totalFileSize = size
                
            else:
                #directory
                realBasePath = os.path.realpath(basePath)
                files = []
                knownFiles = set()
                knownDirs = set((realBasePath,)) #directories which may not be queued for checking again
                toCheck = deque(((tuple(), realBasePath),)) #directories which still need to be checked
                while len(toCheck) > 0 and (not self.shouldAbort):
                    #process one directory
                    try:
                        currentPath, currentRealPath = toCheck.popleft()
                        for pathComponent in os.listdir(currentRealPath):
                            #process one item inside the directory
                            path = currentPath + (pathComponent,)
                            realPath = os.path.join(currentRealPath, pathComponent)
                            if os.path.islink(realPath):
                                #link
                                realPath = os.path.realpath(realPath)
                                
                            if os.path.isfile(realPath):
                                #file
                                if not realPath in knownFiles:
                                    #add file
                                    try:
                                        with open(realPath, 'rb') as fl:
                                            fl.seek(0,2)
                                            size = fl.tell()
                                    except IOError:
                                        raise TorrentCreatorException('Failed to access file "%s" (absolute path "%s")!', os.path.join(*path), realPath)
                                    
                                    self.amountOfFiles += 1
                                    self.totalFileSize += size
                                    files.append((path, realPath, size))
                                    knownFiles.add(realPath)
                                    
                            else:
                                #directory
                                if not realPath in knownDirs:
                                    toCheck.append((path, realPath))
                                    knownDirs.add(realPath)
                        
                    except OSError:
                        raise TorrentCreatorException('IO error while processing the directory "%s" (absolute path "%s")', os.path.join(*currentPath), currentRealPath)
                    
                files.sort()
                
        except OSError:
            raise TorrentCreatorException('General IO error')
        
        return files
        
        
    def _getPieceHashes(self, files, pieceLength):
        pieceHashes = []
        trailingData = ''
        trailingDataLen = 0
        self.currentFileNumber = 0
        
        while self.currentFileNumber < len(files) and (not self.shouldAbort):
            #process one file
            try:
                fileSet = files[self.currentFileNumber]
                previousBytes = self.processedFileSize
                self.currentFileName = os.path.join(*fileSet[0])
                self.currentFileProgress = 0.0
                
                with open(fileSet[1], 'rb') as fl:
                    #hash entire file chunk for chunk
                    data = trailingData + fl.read(pieceLength - trailingDataLen)
                    self.processedFileSize += (len(data) - trailingDataLen)
                    while len(data) == pieceLength and (not self.shouldAbort):
                        #hash one data chunk
                        pieceHashes.append(sha(data).digest())
                        self.currentFileProgress = (self.processedFileSize - previousBytes) / (fileSet[2] * 1.0)
                        data = fl.read(pieceLength)
                        self.processedFileSize += len(data)
                
                if not self.shouldAbort:
                    trailingData = data
                    trailingDataLen = len(trailingData)
                    if fileSet[2] == 0:
                        self.currentFileProgress = 1.0
                    else:
                        self.currentFileProgress = (self.processedFileSize - previousBytes) / (fileSet[2] * 1.0)
                    self.currentFileNumber += 1
                    assert self.currentFileProgress == 1.0, 'Finished with hashing but yet not (read %d bytes, size %d, makes %f)?!' % (readBytes, fileSet[2], self.currentFileProgress)
                            
            except IOError:
                raise TorrentCreatorException('Failed to access file "%s" (absolute path "%s")!', os.path.join(*fileSet[0]), fileSet[1])
            
        if len(trailingData) > 0:
            pieceHashes.append(sha(trailingData).digest())
            
        return ''.join(pieceHashes)
    
    
    def _getTorrentData(self, dataPath, files, pieceHashes, pieceLength, mainTracker, trackerList, creationDate, comment, creator):
        torrentData = {}
        
        #tracker
        torrentData['announce'] = mainTracker.encode('UTF-8')
        if trackerList is not None:
            allTracker = []
            for tier in trackerList:
                allTracker.append([trackerUrl.encode('UTF-8') for trackerUrl in tier])
            torrentData['announce-list'] = allTracker
            
        #other
        torrentData['encoding'] = 'UTF-8'
        if creationDate is not None:
            torrentData['creation date'] = creationDate
        if comment is not None:
            torrentData['comment'] = comment.encode('UTF-8')
        if creator is not None:
            torrentData['created by'] = creator.encode('UTF-8')
            
        #info dict
        info = {}
        info['piece length'] = pieceLength
        info['pieces'] = pieceHashes
        
        if len(files) == 1:
            #single file
            info['name'] = files[0][0][0].encode('UTF-8')
            info['length'] = files[0][2]
        else:
            #multi file
            fileInfo = []
            for fileSet in files:
                filePath = [pathComp.encode('UTF-8') for pathComp in fileSet[0]]
                fileInfo.append({'path':filePath,
                                 'length':fileSet[2]})                    
            info['files'] = fileInfo
            
            info['name'] = os.path.split(dataPath)[-1].encode('UTF-8')
            if info['name'] == '':
                info['name'] = os.path.split(dataPath[:-1])[-1].encode('UTF-8')
            assert not info['name'] == '', 'Name still empty?! Path: "%s"' % (dataPath,)
            
        torrentData['info'] = info
        
        return bencode(torrentData)
    
    
    def _createTorrentFile(self, torrentPath, torrentData):
        try:
            with open(torrentPath, 'wb') as fl:
                fl.write(torrentData)
                
        except IOError:
            raise TorrentCreatorException('Failed to write to torrent file "%s"!', torrentPath)
        
        
    def _create(self, torrentPath, dataPath, pieceLength, mainTracker, trackerList, creationDate, comment, creator):
        self.running = True
        
        try:
            #normalise path
            dataPath = os.path.normpath(os.path.abspath(os.path.expanduser(dataPath)))
            torrentPath = os.path.normpath(os.path.abspath(os.path.expanduser(torrentPath)))
            
            if not self.shouldAbort:
                #get a list of all files which will be in the torrent
                files = self._getFiles(dataPath)
                assert len(files) == self.amountOfFiles, 'Inaccurate length?!'
                if self.amountOfFiles == 0:
                    raise TorrentCreatorException('Torrent would not contain any files!')
            
            if not self.shouldAbort:
                #hash the files
                pieceHashes = self._getPieceHashes(files, pieceLength)
            
            if not self.shouldAbort:
                #generate the torrent data, then save it
                torrentData = self._getTorrentData(dataPath, files, pieceHashes, pieceLength, mainTracker, trackerList, creationDate, comment, creator)
                self._createTorrentFile(torrentPath, torrentData)
            
        except TorrentCreatorException, tce:
            self.lastError = tce
            
        except Exception, e:
            self.lastError = TorrentCreatorException('InternalError:\n%s', logTraceback())
            
        self.running = False
        self.thread = None
        
    
    def getFiles(self, dataPath):
        try:
            dataPath = os.path.normpath(os.path.abspath(os.path.expanduser(dataPath)))
            self._getFiles(dataPath)
            
        except TorrentCreatorException, tce:
            raise tce
        
        except Exception, e:
            raise TorrentCreatorException('InternalError:\n%s', logTraceback())
        
        
    def create(self, torrentPath, dataPath, pieceLength, mainTracker, trackerList=None, creationDate=None, comment=None, creator=None):
        assert type(torrentPath) == unicode, 'path for torrent file not unicode?!'
        assert type(dataPath) == unicode, 'path to files not unicode?!'
        assert pieceLength > 0, 'piece length <= 0 ?!'
        assert self.thread is None, 'thread still running?!'
        
        self.thread = threading.Thread(target=self._create, args=(torrentPath, dataPath, pieceLength, mainTracker, trackerList, creationDate, comment, creator))
        self.thread.start()
        
        
    def abort(self):
        thread = self.thread
        self.shouldAbort = True
        if thread is not None:
            thread.join()
        self.shouldAbort = False
            
            
    def isRunning(self):
        return self.running
    
    
    def getLastError(self):
        return self.lastError
    
    
    def reset(self):
        self.lastError = None
        self.amountOfFiles = 0
        self.currentFileNumber = 0
        self.currentFileName = ''
        self.currentFileProgress = 0.0
        self.processedFileSize = 0
    
    
    def getStats(self):
        stats = {}
        stats['amountOfFiles'] = self.amountOfFiles
        stats['currentFileNumber'] = self.currentFileNumber
        stats['currentFileName'] = self.currentFileName
        stats['currentFileProgress'] = self.currentFileProgress
        stats['totalFileSize'] = self.totalFileSize
        stats['processedFileSize'] = self.processedFileSize
        return stats




if __name__ == '__main__':
    from time import sleep
    
    dataPath = u''
    torrentPath = u''
    pieceLength = 262144
    mainTracker = u'http://'
    
    tc = TorrentCreator()
    tc.create(torrentPath, dataPath, pieceLength, mainTracker)
    
    while tc.isRunning():
        progress = tc.getStats()
        print 'Progress: ',progress['currentFileNumber'],'/',progress['amountOfFiles'],' (',round(progress['currentFileProgress']*100,2),'%)'
        sleep(1)
        
    if tc.getLastError() is None:
        print 'Torrent was successfully created'
    else:
        print 'Creation of torrent failed:'
        raise tc.getLastError()