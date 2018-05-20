from math import log
import random
import time

random.seed(time.time())

C_ALLOC=[8, 8]
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
            return_str=str(hex(self.tag))+'/'+str(hex(self.data))
        return_str=return_str+' {}/{}/{}'.format(self.valid, self.dirty, self.cid)
        return return_str

class line:
    def __init__(self, way):
        self.nway=way
        self.way=[]
        self.lru=[]
        self.miss=[0, 0]
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
            if b.valid and b.tag==tag and b.cid == cid:
                # print 'cache HIT'
                self.lru.remove(i)
                self.lru.append(i)
                b.hit+=1
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
                target.hit+=1
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
                target.hit+=1
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
                b.dirty=1
                b.data=data
                b.hit+=1
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
                target.hit+=1
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
                target.hit+=1
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
        for i in range(self.nway):
            if self.way[i].cid == cid:
                return i

    def evict(self, cid):
        if self.count(cid) < C_ALLOC[cid]:
            return self.get_first_block((cid+1)%2)
        else:
            return self.get_first_block(cid)


class cache:
    def __init__(self, bsize, wnum, lnum, addr_size, mperiod):
        self.line=[]
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
        read_line=self.line[index]
        data=read_line.read(tag, offset, cid)
        self.opnum+=1
        if self.opnum%self.mperiod == 0:
            self.repartition()
        return data

    def write(self, addr, data, cid):
        tag, index, offset=process_addr(addr, self.bsize, self.lnum, self.addr_size)
        write_line=self.line[index]
        success=write_line.write(tag, offset, data, cid)
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
        if line_utility+self.line[lid].miss[cid] != 0:
            return float(line_utility)/(line_utility+self.line[lid].miss[cid])
        return 0

    def repartition(self):
        global C_ALLOC
        max_utility=-float("inf")
        max_alloc=[0,0]
        for i in range(self.wnum-1):
            tmp_utility=0
            for j in range(SET_NUM):
                alloc=i+1
                a_line_utility=self.get_utility_from_line(alloc, j*self.lnum/SET_NUM, 0)
                b_line_utility=self.get_utility_from_line(self.wnum-alloc, j*self.lnum/SET_NUM, 1)
            tmp_utility=a_line_utility+b_line_utility
            if max_utility < tmp_utility:
                max_utility=tmp_utility
                max_alloc=[alloc, self.wnum-alloc]
        C_ALLOC=max_alloc


if __name__=='__main__':
    c=cache(32, 16, 512, 32, 5000)
    '''
    print c.read(0x12345678, 1)
    print c
    print c.write(0x12345678, 0xbb, 1)
    print c
    '''
    idx=0
    while idx<1000000:
        c.read(int(random.random()*0xffffffff), 0 if random.random()<0.7 else 1)
        c.write(int(random.random()*0xffffffff),0xbb, 0 if random.random()<0.7 else 1)
        idx+=1
    print C_ALLOC
