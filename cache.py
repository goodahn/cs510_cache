from math import log
import random
import sys
import time

random.seed(time.time())

CORE_NUM=4
BLOCK_SIZE=8
WAY_NUM=32
LINE_NUM=1024
ADDR_SIZE=64
M_PERIOD=5000000
C_ALLOC=[WAY_NUM/CORE_NUM for i in range(CORE_NUM)]
SET_NUM=32

def process_addr(addr, bsize, lnum, addr_size):
    offset_bit=int(log(bsize, 2))
    index_bit=int(log(lnum, 2))
    tag_bit=addr_size-offset_bit-index_bit
    format_str='{0:0'+str(addr_size)+'b}'
    bin_addr=format_str.format(addr)
    tag=int(bin_addr[:tag_bit], 2)
    index=int(bin_addr[tag_bit:tag_bit+index_bit], 2)
    offset=int(bin_addr[tag_bit+index_bit:], 2)
    return tag, index, offset

class block:
    def __init__(self):
        self.valid=0
        self.dirty=0
        self.data=None
        self.tag=None
        self.cid=None
        self.hit=0
    def __str__(self):
        if self.tag==None:
            return_str='None/None'
        else:
            return_str=str(hex(self.tag))+'/'+str((self.data))
        return_str=return_str+' {}/{}/{}'.format(self.valid, self.dirty, self.cid)
        return return_str

class line:
    def __init__(self, way):
        self.nway=way
        self.way=[]
        self.lru=[]
        self.miss=[0 for i in range(CORE_NUM)]
        for i in xrange(way):
            self.way.append(block())

    def __str__(self):
        return_str=''
        for i in xrange(self.nway):
            return_str+='Way '+str(i)+': '+str(self.way[i])+'  '
        return_str+='LRU: '+str(self.lru)
        return return_str

    def get_available_way(self):
        for i in xrange(self.nway):
            b=self.way[i]
            if b.valid==0:
                return i
        else:
            return None

    def read(self, tag, offset, cid):
        # print 'READ'
        for i in xrange(self.nway):
            b=self.way[i]
            if b.valid and b.tag==tag:
                # print 'cache HIT'
                self.lru.remove(i)
                self.lru.append(i)
                self.way[i].hit+=1
                return b.data
        else:
            # print 'cache MISS'
            write_line=self.get_available_way()
            self.miss[cid]+=1
            if write_line==None:
                t_idx = self.evict(cid)
                target_way=self.lru.pop(t_idx)
                target=self.way[target_way]
                # print 'EVICTION ON WAY '+str(target_way)
                # if target.dirty:
                    # print 'WRITEBACK'
                target.valid=1
                target.dirty=0
                target.data=0xa
                target.tag=tag
                target.cid=cid
                self.lru.append(target_way)
                return target.data
            else:
                # print 'NOT EVICTION'
                # print 'WRITE ON WAY '+str(write_line)
                target=self.way[write_line]
                target.valid=1
                target.dirty=0
                target.data=0xa
                target.tag=tag
                target.cid=cid
                self.lru.append(write_line)
                return target.data

    def write(self, tag, offset, data, cid):
        # print 'WRITE'
        for i in xrange(self.nway):
            b=self.way[i]
            if b.valid and b.tag==tag and b.cid == cid:
                # print 'cache HIT'
                self.lru.remove(i)
                self.lru.append(i)
                self.way[i].dirty=1
                b.data=data
                self.way[i].hit+=1
                return True
        else:
            # print 'cache MISS'
            write_line=self.get_available_way()
            self.miss[cid]+=1
            if write_line==None:
                t_idx=self.evict(cid)
                target_way=self.lru.pop(t_idx)
                target=self.way[target_way]
                # print 'EVICTION ON WAY '+str(target_way)
                # if target.dirty:
                    # print 'WRITEBACK'
                target.valid=1
                target.dirty=1
                target.data=data
                target.tag=tag
                target.cid=cid
                self.lru.append(target_way)
                return True
            else:
                # print 'NOT EVICTION'
                # print 'WRITE ON WAY '+str(write_line)
                target=self.way[write_line]
                target.valid=1
                target.dirty=1
                target.data=data
                target.tag=tag
                target.cid=cid
                self.lru.append(write_line)
                return True
        return False

    def count(self, cid):
        num=0
        for i in range(self.nway):
            if self.way[i].cid == cid:
                num+=1
        return num

    def get_first_block(self, cid):
        for i in range(len(self.lru)):
            if self.way[self.lru[i]].cid == cid:
                return i

    def get_first_block_not(self, cid):
        for i in range(len(self.lru)):
            if self.way[self.lru[i]].cid != cid:
                return i

    def evict(self, cid):
        # print self.count(cid), C_ALLOC
        if self.count(cid) < C_ALLOC[cid] or self.count(cid) == 0:
            # print "evict not mine"
            # print self.get_first_block_not(cid)
            return self.get_first_block_not(cid)
        else:
            # print "evict mine"
            # print self.get_first_block(cid)
            return self.get_first_block(cid)


class cache:
    def __init__(self, cnum, bsize, wnum, lnum, addr_size, mperiod):
        self.line=[]
        self.cnum=cnum
        self.wnum=wnum
        self.lnum=lnum
        self.bsize=bsize
        self.addr_size=addr_size
        self.mperiod=mperiod
        self.opnum=0
        for i in xrange(lnum):
            self.line.append(line(wnum))

    def __str__(self):
        n=0
        return_str=''
        for i in self.line:
            return_str+=str(n)+'|'
            n+=1
            return_str+=str(i)+'\n'
        return return_str

    def read(self, addr, cid):
        tag, index, offset=process_addr(addr, self.bsize, self.lnum, self.addr_size)
        data=self.line[index].read(tag, offset, cid)
        self.opnum+=1
        if self.opnum%self.mperiod == 0:
            self.repartition()
        return data

    def write(self, addr, data, cid):
        tag, index, offset=process_addr(addr, self.bsize, self.lnum, self.addr_size)
        success=self.line[index].write(tag, offset, data, cid)
        self.opnum+=1 
        if self.opnum%self.mperiod == 0:
            self.repartition()
        return success

    def get_utility_from_line(self, alloc, lid, cid):
        line_utility=0
        for k in range(self.wnum):
            try:
                idx=self.line[lid].lru[k]
                if self.line[lid].way[idx].cid == cid:
                    line_utility+=self.line[lid].way[idx].hit
                    alloc-=1
                if alloc==0:
                    # print "alloc need", k, "line_utility", line_utility
                    break
            except:
                # print "lru need", k, "line_utility", line_utility
                break
        # print "for loop done"
        return line_utility

    def get_max_mu(self, p, alloc, balance):
        max_mu=-float("inf")
        req=0
        for j in range(balance):
            mu=self.get_mu_value(p, alloc, alloc+j+1)
            if mu > max_mu:
                max_mu=mu
                req=j+1
        return max_mu, req

    def get_mu_value(self, p, a, b):
        miss_a=0; miss_b=0      
        for i in range(SET_NUM):
            miss_a += self.get_utility_from_line(a, i*LINE_NUM/SET_NUM, p)
            miss_b += self.get_utility_from_line(b, i*LINE_NUM/SET_NUM, p)
        return (miss_b-miss_a)/float(b-a)

    def repartition(self):
        global C_ALLOC
        max_alloc=[1 for i in range(self.cnum)]
        balance=self.wnum - self.cnum
        while balance != 0:
            max_mu=[0 for i in range(self.cnum)]
            blocks_req=[0 for i in range(self.cnum)]
            for i in range(self.cnum):
                alloc=max_alloc[i]
                max_mu[i], blocks_req[i]=self.get_max_mu(i, alloc, balance)
            winner=max_mu.index(max(max_mu))
            max_alloc[winner] += blocks_req[winner]
            balance -= blocks_req[winner]
        C_ALLOC=max_alloc
        print C_ALLOC

    def get_result(self):
        hit=0; miss=0
        for i in range(self.lnum):
            miss+=sum(self.line[i].miss)
            for j in range(self.wnum):
                hit+=self.line[i].way[j].hit

        return miss/float(hit+miss)*100

if __name__=='__main__':
    c=cache(CORE_NUM, BLOCK_SIZE, WAY_NUM, LINE_NUM, ADDR_SIZE, M_PERIOD)
    idx=0
    #f=open('/home/ahn/parsec-3.0/pkgs/apps/freqmine/run/memory_trace.out', 'r')
    f=open('/home/guest/memory_trace_freqmine.out', 'r')
    #f=open('/home/guest/memory_trace_swaptions.out', 'r')
    read_idx=0
    thread_list=dict()
    thread_core=dict()
    thread_id=0
    read_dict=dict()
    write_dict=dict()

    for i in f:
        s=i.split()
        timestamp=str(s[0])
        try:
            tid=s[1]
            int(s[1])
        except:
            print "parse error",i
            continue
        try:
            s[2]
        except:
            print "parse error2", i
            continue
        if int(tid)==294967296:
            continue
        else:
            if s[2]=='tr':
                thread_list[tid]=thread_id
                read_dict[thread_id]=0
                write_dict[thread_id]=0
                thread_core[thread_id]=thread_id%4
                thread_id+=1
            elif s[2]=='m':
                tid=thread_list[s[1]]
                if 'r' in s:
                    idx=s.index('r')
                    try:
                        read_addr=int(s[idx+1])
                        read_size=int(s[idx+2])
                        read_dict[tid]+=1
                        c.read(read_addr, thread_core[tid])
                    except:
                        print "read error", i
                if 'r2' in s:
                    idx=s.index('r2')
                    try: 
                        read_addr=int(s[idx+1])
                        read_dict[tid]+=1
                        c.read(read_addr, thread_core[tid])
                    except:
                        print "read2 error", i
                if 'w' in s:
                    idx=s.index('w')
                    try:
                        write_addr=int(s[idx+1])
                        write_size=int(s[idx+2])
                        write_dict[tid]+=1
                        c.write(write_addr,"bb", thread_core[tid])
                    except:
                        print "write error", i
            elif s[2]=='tf':
                try:
                    del thread_list[s[1]]
                except:
                    print "thread finish error", i
            read_idx+=1
            if read_idx%100000==0:
                print read_idx
    print C_ALLOC
    print c.get_result()
    for i in range(LINE_NUM):
        print c.line[i].miss
