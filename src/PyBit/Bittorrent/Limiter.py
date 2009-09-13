"""
Copyright 2009  Blub

RefillingQuotaLimiter and StaticQuotaLimiter, two classes for distributing available ressources
in a fair way.
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

import threading

class RefillingQuotaLimiter:
    def __init__(self, scheduler, rate, interval=1, maxQuotaRaise=100, maxQuotaReduce=100):
        self.sched = scheduler
        self.rate = int(rate*interval)
        self.interval = int(interval)
        
        self.quota = self.rate
        self.maxQuotaRaise = maxQuotaRaise / 100.0
        self.maxQuotaReduce = maxQuotaReduce / 100.0
        
        self.usedUnits = 0
        self.users = {}        
        
        self.limited = False
        self.anyLimiting = False
        self.lock = threading.Lock()
        
        self.eventId = self.sched.scheduleEvent(self.refill, timedelta=0, repeatdelta=self.interval)
        

    def changeRate(self, newRate):
        self.lock.acquire()
        self.rate = int(newRate*self.interval)
        self.lock.release()

    def addUser(self, ident, callback=None, callbackArgs=[], callbackKw={}):
        self.lock.acquire()
        assert not ident in self.users,'Tried to add second twice'
        self.users[ident]={'usedUnits':0,
                           'limited':False,
                           'callback':callback,
                           'callbackArgs':callbackArgs,
                           'callbackKw':callbackKw}
        self.lock.release()

    def removeUser(self, ident):
        self.lock.acquire()
        del self.users[ident]
        self.lock.release()

    def refill(self):
        self.lock.acquire()
        if len(self.users)>0:
            
            if self.usedUnits>=self.rate:
                #we hit the roof so to speak
                self.limited = True
            else:
                self.limited = False

            quotaLimitedUsers = 0 #users limited due to their Quota
            rateLimitedUsers = 0 #users limited due to the max rate
            unitsUsedByOther = 0

            self.anyLimiting = False
            for user in self.users.itervalues():
                if user['limited']:
                    self.anyLimiting = True
                    if user['usedUnits'] < self.quota:
                        #limited due to the max rate
                        rateLimitedUsers += 1
                    else:
                        #limited due to Quota
                        quotaLimitedUsers += 1
                        
                    user['limited'] = False
                    if user['callback'] is not None:
                        apply(user['callback'], [True]+user['callbackArgs'], user['callbackKw'])
                    
                else:
                    unitsUsedByOther += user['usedUnits']

                user['usedUnits']=0

            if quotaLimitedUsers>0 and self.limited==False:
                #we have a too low quota
                unusedUnits = self.rate - self.usedUnits
                self.quota += max(min((unusedUnits/quotaLimitedUsers), int(self.quota*self.maxQuotaRaise)), 1)
            else:
                if rateLimitedUsers>0:
                    #we have a too high quota
                    newQuota = (self.rate - unitsUsedByOther)/(quotaLimitedUsers+rateLimitedUsers)
                    self.quota -= max(int(self.quota*self.maxQuotaReduce), 1)
                    if newQuota > self.quota:
                        self.quota = newQuota

            self.usedUnits = 0
        self.lock.release()
            
    def claimUnits(self, ident, wantedUnits):
        self.lock.acquire()
        #determine how much may be used
        user = self.users[ident]
        leftQuota = self.quota - user['usedUnits']
        if self.rate - self.usedUnits < leftQuota:
            leftQuota = self.rate - self.usedUnits
        
        #determine how much will be used
        if leftQuota >= wantedUnits:
            #fits in quota
            spendQuota = wantedUnits
        else:
            #too much, exceeds quota
            spendQuota = leftQuota
        
        #add used units
        user['usedUnits'] += spendQuota
        self.usedUnits += spendQuota
        
        #check if we got limited
        if spendQuota < wantedUnits:
            user['limited'] = True
            if user['callback'] is not None:
                apply(user['callback'], [False]+user['callbackArgs'], user['callbackKw'])

        self.lock.release()
        return spendQuota

    def hasLimited(self):
        return self.limited

    def hasLimitedAnything(self):
        return self.anyLimiting
    
    def stop(self, clearAll=True):
        self.lock.acquire()
        if self.eventId is not None:
            self.sched.removeEvent(self.eventId)
            self.eventId = None
            if clearAll:
                self.quota = self.rate
                self.usedUnits = 0
                self.users = {}                
                self.limited = False
                self.anyLimiting = False
        self.lock.release()
        
    def start(self):
        self.lock.acquire()
        self.eventId = self.sched.scheduleEvent(self.recalculateQuota, timedelta=0, repeatdelta=self.interval)
        self.lock.release()




class StaticQuotaLimiter:
    def __init__(self, scheduler, limit, interval=1, maxQuotaRaise=100, maxQuotaReduce=100):
        self.sched = scheduler
        self.limit = int(limit)
        self.interval = int(interval)
        
        self.quota = self.limit
        self.maxQuotaRaise = maxQuotaRaise / 100.0
        self.maxQuotaReduce = maxQuotaReduce / 100.0
        
        self.usedUnits = 0
        self.users = {}        
        
        self.limited = False
        self.anyLimiting = False
        self.lock = threading.Lock()
        
        self.eventId = self.sched.scheduleEvent(self.recalculateQuota, timedelta=0, repeatdelta=self.interval)

    def changeLimit(self, newLimit):
        self.lock.acquire()
        self.quota = int(self.quota*int(newLimit)/(self.limit*1.0))
        self.limit = int(newLimit)
        self.lock.release()

    def addUser(self, ident, callback=None, callbackArgs=[], callbackKw={}):
        self.lock.acquire()
        assert not ident in self.users,'Tried to add ident a second time'
        self.users[ident]={'usedUnits':0,
                           'limited':False,
                           'callback':callback,
                           'callbackArgs':callbackArgs,
                           'callbackKw':callbackKw}
        self.lock.release()

    def removeUser(self, ident):
        self.lock.acquire()
        del self.users[ident]
        self.lock.release()

    def recalculateQuota(self):
        if len(self.users)>0:
            
            if self.usedUnits>=self.limit:
                #we hit the roof so to speak
                self.limited = True
            else:
                self.limited = False

            quotaLimitedUsers = 0 #users limited due to their Quota
            rateLimitedUsers = 0 #users limited due to the max rate
            unitsUsedByOther = 0

            self.anyLimiting = False
            for user in self.users.itervalues():
                if user['limited']:
                    self.anyLimiting = True
                    if user['usedUnits'] < self.quota:
                        #limited due to the max rate
                        rateLimitedUsers += 1
                    else:
                        #limited due to Quota
                        quotaLimitedUsers += 1
                        
                    user['limited'] = False
                    if user['callback'] is not None:
                        apply(user['callback'], [True]+user['callbackArgs'], user['callbackKw'])
                    
                else:
                    unitsUsedByOther += user['usedUnits']

            if quotaLimitedUsers>0 and self.limited==False:
                #we have a too low quota
                unusedUnits = self.rate - self.usedUnits
                self.quota += min((unusedUnits/quotaLimitedUsers), max(int(self.rate*self.maxQuotaRaise), 1))
            else:
                if rateLimitedUsers>0:
                    #we have a too high quota
                    newQuota = (self.rate - unitsUsedByOther)/(quotaLimitedUsers+rateLimitedUsers)
                    self.quota -= max(int(self.rate*self.maxQuotaReduce), 1)
                    if newQuota > self.quota:
                        self.quota = newQuota

            
    def claimUnits(self, ident, wantedUnits):
        self.lock.acquire()
        #determine how much may be used
        user = self.users[ident]
        leftQuota = self.quota - user['usedUnits']
        if self.limit - self.usedUnits < leftQuota:
            leftQuota = self.limit - self.usedUnits
        
        #determine how much will be used
        if leftQuota >= wantedUnits:
            #fits in quota
            spendQuota = wantedUnits
        else:
            #too much, exceeds quota
            spendQuota = leftQuota
        
        #add used units to counters
        user['usedUnits'] += spendQuota
        self.usedUnits += spendQuota
        
        #check if we got limited
        if spendQuota < wantedUnits:
            user['limited'] = True
            if user['callback'] is not None:
                apply(user['callback'], [False]+user['callbackArgs'], user['callbackKw'])
        
        self.lock.release()
        return spendQuota
    
    def releaseUnits(self, ident, units):
        self.lock.acquire()
        
        user = self.users[ident]        
        assert user['usedUnits'] >= units,'Releasing units which were never claimed?!'
        
        user['usedUnits'] -= units
        self.usedUnits -= units
        
        if user['limited'] and user['usedUnits'] <= self.quota:
            #were limited but are now below the limit (or match it)
            user['limited'] = False
            apply(user['callback'], [True]+user['callbackArgs'], user['callbackKw'])
            
        self.lock.release()

    def hasLimited(self):
        return self.limited

    def hasLimitedAnything(self):
        return self.anyLimiting
    
    def stop(self, clearAll=True):
        self.lock.acquire()
        if self.eventId is not None:
            self.sched.removeEvent(self.eventId)
            self.eventId = None
            if clearAll:
                self.quota = self.limit
                self.usedUnits = 0
                self.users = {}                
                self.limited = False
                self.anyLimiting = False
        self.lock.release()
        
    def start(self):
        self.lock.acquire()
        self.eventId = self.sched.scheduleEvent(self.recalculateQuota, timedelta=0, repeatdelta=self.interval)
        self.lock.release()