"""
Copyright 2009  Blub

FilePriority, a class which is used to manage which file should be downloaded and the priority of each file.
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

from Logger import Logger

class FilePriority:
    def __init__(self, btPersister, version, pieceStatus, ownStatus, torrent, torrentIdent):
        self.btPersister = btPersister
        self.version = version
        self.pieceStatus = pieceStatus
        self.ownStatus = ownStatus
        self.torrent = torrent
        
        self.log = Logger('FilePriority', '%-6s - ', torrentIdent)
        
        #load file info
        self.fileInfo = self._loadPersistedData()
        if self.fileInfo is None:
            #nothing stored, create info from scratch
            self.log.debug('No stored file info found, creating it from scratch')
            files = torrent.getFiles()
            pieceLength = torrent.getPieceLength()
            self.fileInfo = []
            for file in files:
                self.fileInfo.append({'firstPiece':file['offset'] / pieceLength,
                                      'lastPiece':(file['offset'] + file['size']) / pieceLength,
                                      'wanted':True,
                                      'priority':0})
            self._persist()
        
        else:
            #retrieved stored info, reapply it
            for fileId in xrange(0, len(self.fileInfo)):
                info = self.fileInfo[fileId]
                if not info['priority'] == 0:
                    self._applyPriority(fileId, info)
                self._applyWantedFlag(fileId, info)
    
    
    ##internal functions - persisting
    
    def _updatePersistedData(self, perstData, currentVersion):
        return perstData[0]
                
                
    def _loadPersistedData(self):
        perstData = self.btPersister.get('FilePriority-fileInfo', None)
        if perstData is not None:
            perstData = self._updatePersistedData(perstData, self.version)
        return perstData
                    
                    
    def _persist(self):
        self.btPersister.store('FilePriority-fileInfo', (self.fileInfo, self.version))
    
    
    ##internal functions - files
                
    def _applyPriority(self, fileId, info):
        firstPiece = info['firstPiece']
        lastPiece = info['lastPiece']
        priority = info['priority']
        firstPiecePrio = priority
        lastPiecePrio = priority
        
        self.log.debug('Setting prio of file %i to %i', fileId, priority)
        
        #firstPiece - find highest prio of all files with the same piece
        idx = fileId - 1
        while idx >= 0:
            if not self.fileInfo[idx]['lastPiece'] == firstPiece:
                #different piece, break
                break
            elif self.fileInfo[idx]['priority'] > priority:
                #higher prio and same piece
                firstPiecePrio = self.fileInfo[idx]['priority']
                break
            idx -= 1
            
        #lastPiece - find highest prio of all files with the same piece
        idx = fileId + 1
        while idx < len(self.fileInfo):
            if not self.fileInfo[idx]['firstPiece'] == lastPiece:
                #different piece, break
                break
            elif self.fileInfo[idx]['priority'] > priority:
                #higher prio and same piece
                lastPiecePrio = self.fileInfo[idx]['priority']
                break
            idx -= 1
            
        #set the priority of the various pieces
        if firstPiece == lastPiece:
            #combine firstPiecePrio and lastPiecePrio, its the same piece
            piecePrio = max(firstPiecePrio, lastPiecePrio)
            self.log.debug('Setting prio of (first and last) piece %i to %i', firstPiece, piecePrio)
            self.pieceStatus.setPriority((firstPiece,), piecePrio)
        else:
            #set priority of first and last piece seperatly
            self.log.debug('Setting prio of first piece %i to %i', firstPiece, firstPiecePrio)
            self.pieceStatus.setPriority((firstPiece,), firstPiecePrio)
            self.log.debug('Setting prio of last piece %i to %i', lastPiece, lastPiecePrio)
            self.pieceStatus.setPriority((lastPiece,), lastPiecePrio)
            
            if lastPiece - firstPiece > 1:
                #more pieces involved
                self.log.debug('Setting prio of remaining piece %i-%i to %i', firstPiece + 1, lastPiece - 1, priority)
                self.pieceStatus.setPriority(xrange(firstPiece + 1, lastPiece), priority)
                
                
    def _applyWantedFlag(self, fileId, info):
        firstPiece = info['firstPiece']
        lastPiece = info['lastPiece']
        wanted = info['wanted']
        firstPieceWanted = wanted
        lastPieceWanted = wanted
        
        self.log.debug('Setting wanted flag of file %i to %i', fileId, wanted)
        
        if not firstPieceWanted:
            #firstPiece - check wanted flag of all files with the same piece
            idx = fileId - 1
            while idx >= 0:
                if not self.fileInfo[idx]['lastPiece'] == firstPiece:
                    #different piece, break
                    break
                elif self.fileInfo[idx]['wanted']:
                    #piece is wanted for this file
                    firstPieceWanted = True
                    break
                idx -= 1
            
        if not lastPieceWanted:
            #lastPiece - check wanted flag of all files with the same piece
            idx = fileId + 1
            while idx < len(self.fileInfo):
                if not self.fileInfo[idx]['firstPiece'] == lastPiece:
                    #different piece, break
                    break
                elif self.fileInfo[idx]['wanted']:
                    #piece is wanted for this file
                    lastPieceWanted = True
                    break
                idx -= 1
            
        #set the wanted flag of the various pieces
        if firstPiece == lastPiece:
            #combine firstPieceWanted and lastPieceWanted, its the same piece
            pieceWanted = firstPieceWanted or lastPieceWanted
            self.log.debug('Setting wanted flag of (first and last) piece %i to %i', firstPiece, pieceWanted)
            self.ownStatus.setPieceWantedFlag((firstPiece,), pieceWanted)
        else:
            #set priority of first and last piece seperatly
            self.log.debug('Setting wanted flag of first piece %i to %i', firstPiece, firstPieceWanted)
            self.ownStatus.setPieceWantedFlag((firstPiece,), firstPieceWanted)
            self.log.debug('Setting wanted flag of last piece %i to %i', lastPiece, lastPieceWanted)
            self.ownStatus.setPieceWantedFlag((lastPiece,), lastPieceWanted)
            
            if lastPiece - firstPiece > 1:
                #more pieces involved
                self.log.debug('Setting wanted flag of remaining piece %i-%i to %i', firstPiece + 1, lastPiece - 1, wanted)
                self.ownStatus.setPieceWantedFlag((pieceIndex for pieceIndex in xrange(firstPiece + 1, lastPiece)), wanted)
    
    
    ##external functions - files
                
    def setFilePriority(self, fileId, priority):
        info = self.fileInfo[fileId]
        info['priority'] = priority
        self._applyPriority(fileId, info)
        self._persist()
        
        
    def setFileWantedFlag(self, fileId, wanted):
        info = self.fileInfo[fileId]
        info['wanted'] = wanted
        self._applyWantedFlag(fileId, info)
        self._persist()
        
        
    ##external functions - stats
        
    def getStats(self):
        files = self.torrent.getFiles()
        pieceSize = self.torrent.getPieceLength()
        lastTorrentPiece = self.torrent.getTotalAmountOfPieces()-1
        lastTorrentPieceSizeDiff = pieceSize - self.torrent.getLengthOfPiece(lastTorrentPiece)
        stats = []
        
        for idx in xrange(0, len(files)):
            firstPiece = self.fileInfo[idx]['firstPiece']
            lastPiece = self.fileInfo[idx]['lastPiece']
            
            neededPieces = set(xrange(firstPiece, lastPiece + 1))
            gotPieces = self.ownStatus.getMatchingGotPieces(neededPieces)
            neededBytes = len(neededPieces) * pieceSize
            if lastTorrentPiece in neededPieces:
                neededBytes -= lastTorrentPieceSizeDiff
            gotBytes = len(gotPieces) * pieceSize
            if lastTorrentPiece in gotPieces:
                gotBytes -= lastTorrentPieceSizeDiff
            progress = (gotBytes * 100.0) / neededBytes
            
            stats.append({'id':idx,
                          'path':files[idx]['path'],
                          'size':files[idx]['size'],
                          'progress':progress,
                          'firstPiece':firstPiece,
                          'lastPiece':lastPiece,
                          'wanted':self.fileInfo[idx]['wanted'],
                          'priority':self.fileInfo[idx]['priority']})
        return stats