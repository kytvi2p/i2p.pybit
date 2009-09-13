"""
Copyright 2009  Blub

ObjectPersister, a general class for storing and retrieving data in/from a sqlite database.
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
from collections import deque
from sqlite3 import dbapi2 as sqlite
import logging
import os
import threading

from Bittorrent.Bencoding import bencode, bdecode


class SimpleObjectPersister:
    def __init__(self, dbPath, log=None):
        self.dbPath = dbPath
        if type(log)==str:
            self.log = logging.getLogger(log)        
        else:
            self.log = log
        
        #load db
        if not os.path.isfile(self.dbPath):
            #database doesn't exist
            if self.log is not None:
                self.log.info("Database not found, creating one")
            self._initDatabase()
            
        self.dbLock = threading.Lock()
    
    
    ##internal functions - db
        
        
    def _preDbQueryJobs(self):
        db = sqlite.connect(self.dbPath)
        db.row_factory = sqlite.Row
        db.text_factory = str
        return db
    
    
    def _postDbQueryJobs(self, db):
        db.close()
        
        
    def _initDatabase(self):
        db = self._preDbQueryJobs()
        db.execute('CREATE TABLE dict ('\
                   'key TEXT PRIMARY KEY,'\
                   'value BINARY'\
                   ');')
        db.commit()
        self._postDbQueryJobs(db)
        
        
    def _dbLoad(self, key):
        db = self._preDbQueryJobs()
        self.log.debug('Getting value for key "%s"', str(key))
        cursor = db.execute('SELECT value FROM dict WHERE key=?', (key,))
        result = cursor.fetchone()
        if result is not None:
            result = result['value']
        self.log.debug('Got value "%s"', str(result))
        self._postDbQueryJobs(db)
        return result
        
        
    def _dbStore(self, key, value):
        with self.dbLock:
            db = self._preDbQueryJobs()
            self.log.debug('Storing key "%s" with value "%s"', str(key), str(value))
            cursor = db.execute('SELECT key FROM dict WHERE key=?', (key,))
            if cursor.fetchone() is None:
                #doesn't exist yet, insert
                db.execute('INSERT INTO dict VALUES (?, ?)', (key, value))
            else:
                #already exists, update
                db.execute('UPDATE dict SET value=? WHERE key=?', (value, key))
            db.commit()
            self._postDbQueryJobs(db)
    
    
    ##external functions - db
    
    def load(self, key):
        dbResult = self._dbLoad(key)
        if dbResult is None:
            #unknown key
            raise Exception('Unknown key!')
        
        obj = bdecode(dbResult, extended=True)
        return obj
    
    
    def store(self, key, value):
        data = bencode(value, extended=True)
        self._dbStore(key, data)
        
    
    ##external functions - dict
    
    def get(self, key, default=None):
        try:
            result = self.load(key)
        except:
            result = default
        return result





class ThreadedObjectPersister(SimpleObjectPersister):
    def __init__(self, dbPath, log=None):
        SimpleObjectPersister.__init__(self, dbPath, log)
        
        #locks
        self.queueLock = threading.Lock() #protects queue-functions from concurrent access
        self.writeLock = threading.Lock() #either held by a 'manual' store (sync=True) or by a store from the thread
        
        #events
        self.storeEvent = threading.Event()
    
        #queue
        self.currentStore = None  #item which is currently stored
        self.queuedStores = {}    #key/data pairs which still need to be stored
        self.storeQueue = deque() #list of keys which will be stored according to the ordering of the list
        
        #thread
        self.thread = None
        
        
    ##internal functions - queue
    
    def _addToQueue(self, key, data):
        self.queueLock.acquire()
        if key in self.queuedStores:
            #already queued for store, just update the value and
            #ensure that the store is active
            self.queuedStores[key]['data'] = data
            self.queuedStores[key]['queueItem'][1] = True
        
        else:
            #not yet in queue
            item = {'data':data,
                    'queueItem':[key, True]}
            self.queuedStores[key] = item
            self.storeQueue.append(item['queueItem'])
            
            if len(self.storeQueue) == 1:
                #first item, notify thread
                self.storeEvent.set()
                
        self.queueLock.release()
        
        
    def _removeFromQueue(self, key):
        self.queueLock.acquire()
        if key in self.queuedStores:
            self.queuedStores[key]['queueItem'][1] = False
        self.queueLock.release()
            
        
    def _getFromQueue(self, key):
        self.queueLock.acquire()
        data = None
        if key in self.queuedStores:
            #queued store exists
            if self.queuedStores[key]['queueItem'][1] == True:
                data = self.queuedStores[key]['data']
            
        if data is None and self.currentStore is not None:
            #something is currently stored
            if self.currentStore[0] == key:
                data = self.currentStore[1]
        self.queueLock.release()
        return data
    
    
    def _getNextFromQueue(self):
        self.queueLock.acquire()
        item = None
        while item is None and len(self.storeQueue) > 0:
            key, active = self.storeQueue.popleft()
            if active:
                item = (key, self.queuedStores[key]['data'])
                del self.queuedStores[key]
                self.currentStores = item
        
        self.storeEvent.clear()
        self.queueLock.release()
        return item
        
        
    def _clearCurrentStore(self):
        self.queueLock.acquire()
        self.currentStore = None
        self.queueLock.release()
        
        
    ##internal functions - thread
    
    def run(self):
        self.writeLock.acquire()
        while not self.shouldStop:
            item = self._getNextFromQueue()
            if item is None:
                #nothing to do, wait
                self.writeLock.release()
                self.storeEvent.wait()
                self.writeLock.acquire()
            else:
                #do one store
                self._dbStore(item[0], item[1])
                self._clearCurrentStore()
                
        self.thread = None
        self.writeLock.release()
    
    def _start(self):
        self.writeLock.acquire()
        self.shouldStop = False
        if self.thread is None:
            self.thread = threading.Thread(target=self.run)
            self.thread.start()
        self.writeLock.release()
            
    
    def _stop(self):
        self.writeLock.acquire()
        self.shouldStop = True
        self.storeEvent.set()
        thread = self.thread
        self.writeLock.release()
        thread.join()
        
        
        
    ##internal functions - load/store
    
    def _store(self, key, data, sync):
        if not sync:
            #async, store done by thread
            self._addToQueue(key, data)
        
        else:
            #sync, do directly
            self.writeLock.acquire()
            self._removeFromQueue(key)
            self._dbStore(key, data)
            self.writeLock.remove()
            
            
    def _load(self, key):
        data = self._getFromQueue(key)
        if data is None:
            #meh, need to get it from disk
            data = self._dbLoad(key)
        return data
    
    
    ##external functions - db
    
    def load(self, key):
        dbResult = self._load(key)
        if dbResult is None:
            #unknown key
            raise Exception('Unknown key!')
        
        obj = bdecode(dbResult, extended=True)
        return obj
    
    
    def store(self, key, value, sync=False):
        """
        sync = store data to disk immediately
        """
        data = bencode(value, extended=True)
        self._store(key, data, sync)
        
        
    def close(self):
        self._dbClose()
        
    
    ##external functions - dict
    
    def get(self, key, default=None):
        try:
            result = self.load(key)
        except:
            result = default
        return result
    
    
    ##external functions - thread
    
    def start(self):
        self._start()
        
        
    def stop(self):
        self._stop()