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
from base64 import b64encode, b64decode
from collections import deque
from sqlite3 import OperationalError, dbapi2 as sqlite
import logging
import os
import re
import threading

from Bittorrent.Bencoding import bencode, bdecode




def regexCheck(expression, string):
    return (re.search(expression, string) is not None)




class ObjectPersisterException(Exception):
    def __init__(self, reason, *args):
        self.reason = reason % args
        Exception.__init__(self, self.reason)




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
        else:
            #database exists
            self._checkDatabase()
            
        self.dbLock = threading.Lock()
    
    
    ##internal functions - db - basic
        
    def _preDbQueryJobs(self):
        db = sqlite.connect(self.dbPath)
        db.row_factory = sqlite.Row
        db.text_factory = str
        db.create_function("regexp", 2, regexCheck)
        return db
    
    
    def _postDbQueryJobs(self, db):
        db.close()
        
        
    def _initDatabase(self):
        db = self._preDbQueryJobs()
        db.execute('CREATE TABLE dict ('\
                   'key TEXT PRIMARY KEY,'\
                   'value TEXT,'\
                   'encoding TEXT'\
                   ');')
        db.commit()
        self._postDbQueryJobs(db)
        
        
    def _checkDatabase(self):
        db = self._preDbQueryJobs()
        try:
            cursor = db.execute('SELECT encoding FROM dict LIMIT 1')
        except OperationalError, oe:
            #missing column
            self.log.info('Table check returned "%s", updating table structure by adding column "encoding"', str(oe))
            db.execute('ALTER TABLE dict ADD COLUMN encoding TEXT')
            db.commit()
            db.execute('UPDATE dict SET encoding=?', ('bencode',))
            db.commit()
        self._postDbQueryJobs(db)
        
        
    ##internal functions - db - actions
    
    def _dbKeys(self, regex):
        db = self._preDbQueryJobs()
        if regex is None:
            #get all keys
            self.log.debug('Getting all keys')
            cursor = db.execute('SELECT key FROM dict')
            results = cursor.fetchall()
        else:
            #only get the keys matching the given regex
            self.log.debug('Getting keys which match regex "%s"', regex)
            cursor = db.execute('SELECT key FROM dict WHERE key REGEXP ?', (regex,))
            results = cursor.fetchall()
        results = [result[0] for result in results]
        self._postDbQueryJobs(db)
        return results
        
        
    def _dbLoad(self, key):
        db = self._preDbQueryJobs()
        self.log.debug('Getting value for key "%s"', str(key))
        cursor = db.execute('SELECT value, encoding FROM dict WHERE key=?', (key,))
        result = cursor.fetchone()
        if result is not None:
            result = (result['value'], result['encoding'])
            self.log.debug('Got value "%s" with encoding "%s"', str(result[0]), str(result[1]))
        else:
            self.log.debug('Key doesn\'t exist')
        self._postDbQueryJobs(db)
        return result
        
        
    def _dbStore(self, key, value, encoding):
        with self.dbLock:
            db = self._preDbQueryJobs()
            self.log.debug('Storing key "%s" with value "%s" and encoding "%s"', str(key), str(value), encoding)
            cursor = db.execute('SELECT key FROM dict WHERE key=?', (key,))
            if cursor.fetchone() is None:
                #doesn't exist yet, insert
                db.execute('INSERT INTO dict VALUES (?, ?, ?)', (key, value, encoding))
            else:
                #already exists, update
                db.execute('UPDATE dict SET value=?, encoding=? WHERE key=?', (value, encoding, key))
            db.commit()
            self._postDbQueryJobs(db)
            
            
    def _dbRemove(self, key):
        removed = False
        with self.dbLock:
            db = self._preDbQueryJobs()
            cursor = db.execute('SELECT key FROM dict WHERE key=?', (key,))
            if cursor.fetchone() is None:
                self.log.debug('Should remove key "%s" but key doesn\'t exist!', str(key))
            else:
                self.log.debug('Removing key "%s"', str(key))
                db.execute('DELETE FROM dict WHERE key=?', (key,))
                db.commit()
                removed = True
            self._postDbQueryJobs(db)
        return removed
    
    
    ##internal functions - conversion
    
    def _objToString(self, obj, encoding):
        value = bencode(obj, extended=True)
        if encoding == 'base64':
            value = b64encode(value)
        return value
    
    
    def _stringToObj(self, value, encoding):
        if encoding == 'base64':
            value = b64decode(value)
        obj = bdecode(value, extended=True)
        return obj
    
    
    ##external functions - db
    
    def keys(self, regex=None):
        result = self._dbKeys(regex)
        result.sort()
        return result
    
    
    def load(self, key):
        dbResult = self._dbLoad(key)
        if dbResult is None:
            #unknown key
            raise ObjectPersisterException("key doesn't exist")
        
        obj = self._stringToObj(dbResult[0], dbResult[1])
        return obj
    
    
    def store(self, key, obj, encoding='base64'):
        value = self._objToString(obj, encoding)
        self._dbStore(key, value, encoding)
        
        
    def remove(self, key, strict=False):
        removed = self._dbRemove(key)
        if strict and not removed:
            raise ObjectPersisterException("key doesn't exist")
        return removed
        
    
    ##external functions - dict
    
    def get(self, key, default=None):
        try:
            result = self.load(key)
        except ObjectPersisterException, ope:
            result = default
        return result





class ThreadedObjectPersister(SimpleObjectPersister):
    def __init__(self, dbPath, log=None):
        SimpleObjectPersister.__init__(self, dbPath, log)
        
        #locks
        self.queueLock = threading.Lock() #protects queue-functions from concurrent access
        self.writeLock = threading.Lock() #either held by a 'manual' store (sync=True) or by a store from the thread
        
        #events
        self.jobEvent = threading.Event()
    
        #queue
        self.currentJob = None  #job which is currently processed
        self.queuedJobs = {}    #jobs which still need to be processed
        self.jobQueue = deque() #list of keys which will be processed according to the ordering of the list
        
        #thread
        self.thread = None
        
        
    ##internal functions - queue
    
    def _addRemoveJobToQueue(self, key):
        self.queueLock.acquire()
        if key in self.queuedJobs:
            #already queued, deactivate old job
            self.queuedJobs[key]['queueItem'][1] = False
        
        elif len(self.jobQueue) == 0:
            #first item, notify thread
            self.jobEvent.set()
            
        #add to queue
        item = {'action':'remove',
                'queueItem':[key, True]}
        self.queuedJobs[key] = item
        self.jobQueue.append(item['queueItem'])
        
        self.queueLock.release()
        
        
    def _addStoreJobToQueue(self, key, value, encoding):
        self.queueLock.acquire()
        if key in self.queuedJobs:
            #already queued, deactivate old job
            self.queuedJobs[key]['queueItem'][1] = False
            
        elif len(self.jobQueue) == 0:
            #first item, notify thread
            self.jobEvent.set()
                
        #add to queue
        item = {'action':'store',
                'value':value,
                'encoding':encoding,
                'queueItem':[key, True]}
        self.queuedJobs[key] = item
        self.jobQueue.append(item['queueItem'])
        
        self.queueLock.release()
        
        
    def _removeJobFromQueue(self, key):
        self.queueLock.acquire()
        if key in self.queuedJobs:
            self.queuedJobs[key]['queueItem'][1] = False
            del self.queuedJobs[key]
        self.queueLock.release()
        
        
    def _getJobFromQueue(self, key):
        #returns the latest queued action for this key, if any
        self.queueLock.acquire()
        result = None
        if key in self.queuedJobs:
            #queued job exists
            assert job['queueItem'][1], 'inactive job but job data still there?!'
            job = self.queuedJobs[key].copy()
            del result['queueItem']
            
        if result is None and self.currentJob is not None:
            #something is currently processed
            if self.currentJob['key'] == key:
                result = self.currentJob.copy()
                del result['key']
        self.queueLock.release()
        return result
        
    
    def _getAllKeysFromQueue(self, action):
        #return all jobs which are queued with the given action
        self.queueLock.acquire()
        result = [key for key, job in self.queuedJobs.iteritems() if job['action'] == action]
        self.queueLock.release()
        return result
    
    
    def _getNextJobFromQueue(self):
        self.queueLock.acquire()
        item = None
        while item is None and len(self.jobQueue) > 0:
            key, active = self.jobQueue.popleft()
            if active:
                item = self.queuedJobs[key]
                del self.queuedJobs[key]
                del item['queueItem']
                item['key'] = key
                self.currentJobs = item
        
        self.jobEvent.clear()
        self.queueLock.release()
        return item
        
        
    def _clearCurrentJob(self):
        self.queueLock.acquire()
        self.currentJob = None
        self.queueLock.release()
        
        
    ##internal functions - thread
    
    def _processJob(self, item):
        assert item['action'] in ('store', 'remove'), 'Invalid action "%s"!' % (item['action'],)
        if item['action'] == 'store':
            self._dbStore(item['key'], item['value'], item['encoding'])
        elif item['action'] == 'remove':
            self._dbRemove(item['key'])
        self._clearCurrentJob()
        
        
    def run(self):
        self.writeLock.acquire()
        while not self.shouldStop:
            item = self._getNextJobFromQueue()
            if item is None:
                #nothing to do, wait
                self.writeLock.release()
                self.jobEvent.wait()
                self.writeLock.acquire()
            else:
                #process job
                self._processJob(item)
        
        self.log.debug('Processing all currently queued jobs')
        
        #process remaining jobs
        item = self._getNextJobFromQueue()
        while item is not None:
            self._processJob(item)
            item = self._getNextJobFromQueue()
        
        self.log.debug('Stopping')
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
        self.jobEvent.set()
        thread = self.thread
        self.writeLock.release()
        thread.join()
        
        
        
    ##internal functions - db
    
    def _keys(self, regex):
        dbResults = set(self._dbKeys(regex))
        queuedStores = self._getAllKeysFromQueue('store')
        queuedRemoves = self._getAllKeysFromQueue('remove')
        if regex is not None:
            matchObj = re.compile(regex)
            queuedStores = (key for key in queuedStores if matchObj.match(key) is not None)
            queuedRemoves = (key for key in queuedRemoves if matchObj.match(key) is not None)
        queuedStores = set(queuedStores)
        queuedRemoves = set(queuedRemoves)
        result = list((dbResults.union(queuedStores)).difference(queuedRemoves))
        result.sort()
        return result
        
    
    def _store(self, key, value, encoding, sync):
        if not sync:
            #async, store done by thread
            self._addStoreJobToQueue(key, value, encoding)
        
        else:
            #sync, do directly
            self.writeLock.acquire()
            self._removeJobFromQueue(key)
            self._dbStore(key, value, encoding)
            self.writeLock.release()
            
            
    def _remove(self, key, sync):
        removed = False
        if not sync:
            #async, remove done by thread
            self._addRemoveJobToQueue(key)
        
        else:
            #sync, do directly
            self.writeLock.acquire()
            self._removeJobFromQueue(key)
            removed = self._dbRemove(key)
            self.writeLock.release()
        return removed
            
            
    def _load(self, key):
        result = self._getJobFromQueue(key)
        if result is None:
            #meh, need to get it from disk
            result = self._dbLoad(key)
            
        elif result['action'] == 'remove':
            result = None
            
        return result
    
    
    ##external functions - db
    
    def keys(self, regex=None):
        return self._keys(regex)
    
    
    def load(self, key):
        dbResult = self._load(key)
        if dbResult is None:
            #unknown key
            raise ObjectPersisterException('Unknown key!')
        
        obj = self._stringToObj(dbResult[0], dbResult[1])
        return obj
    
    
    def store(self, key, obj, encoding='base64', sync=False):
        """
        sync = store data to disk immediately
        """
        value = self._objToString(obj, encoding)
        self._store(key, value, encoding, sync)
        
    
    def remove(self, key, strict=False, sync=False):
        if strict and (not sync):
            removed = (self._load(key) is not None)
            self._remove(key, sync)
        else:
            removed = self._remove(key, sync)
        
        if strict and not removed:
            raise ObjectPersisterException("key doesn't exist")
        return removed
        
    
    ##external functions - dict
    
    def get(self, key, default=None):
        try:
            result = self.load(key)
        except ObjectPersisterException, ope:
            result = default
        return result
    
    
    ##external functions - thread
    
    def start(self):
        self._start()
        
        
    def stop(self):
        self._stop()