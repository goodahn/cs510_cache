from math import log

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
    def __str__(self):
        if self.tag==None:
            return_str='None/None'
        else:
            return_str=str(hex(self.tag))+'/'+str(hex(self.data))
        return_str=return_str+' {}/{}'.format(self.valid, self.dirty)
        return return_str

class line:
    def __init__(self, way):
        self.nway=way
        self.way=[]
        self.lru=[]
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

    def read(self, tag, offset):
        print 'READ'
        for i in xrange(self.nway):
            b=self.way[i]
            if b.valid and b.tag==tag:
                print 'cache HIT'
                self.lru.remove(i)
                self.lru.append(i)
                return b.data
        else:
            print 'cache MISS'
            write_line=self.get_available_way()
            if write_line==None:
                target_way=self.lru.pop(0)
                target=self.way[target_way]
                print 'EVICTION ON WAY '+str(target_way)
                if target_way.dirty:
                    print 'WRITEBACK'
                target.valid=1
                target.dirty=0
                target.data=0xa
                target.tag=tag
                self.lru.append(target_way)
                return target.data
            else:
                print 'NOT EVICTION'
                print 'WRITE ON WAY '+str(write_line)
                target=self.way[write_line]
                target.valid=1
                target.dirty=0
                target.data=0xa
                target.tag=tag
                self.lru.append(write_line)
                return target.data

    def write(self, tag, offset, data):
        print 'WRITE'
        for i in xrange(self.nway):
            b=self.way[i]
            if b.valid and b.tag==tag:
                print 'cache HIT'
                self.lru.remove(i)
                self.lru.append(i)
                b.dirty=1
                b.data=data
                return True
        else:
            print 'cache MISS'
            write_line=self.get_available_way()
            if write_line==None:
                target_way=self.lru.pop(0)
                target=self.way[target_way]
                print 'EVICTION ON WAY '+str(target_way)
                if target_way.dirty:
                    print 'WRITEBACK'
                target.valid=1
                target.dirty=1
                target.data=data
                target.tag=tag
                self.lru.append(target_way)
                return True
            else:
                print 'NOT EVICTION'
                print 'WRITE ON WAY '+str(write_line)
                target=self.way[write_line]
                target.valid=1
                target.dirty=1
                target.data=data
                target.tag=tag
                self.lru.append(write_line)
                return True
        return False




class cache:
    def __init__(self, bsize, wnum, lnum, addr_size):
        self.line=[]
        self.wnum=wnum
        self.lnum=lnum
        self.bsize=bsize
        self.addr_size=addr_size
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

    def read(self, addr):
        tag, index, offset=process_addr(addr, self.bsize, self.lnum, self.addr_size)
        read_line=self.line[index]
        return read_line.read(tag, offset)

    def write(self, addr, data):
        tag, index, offset=process_addr(addr, self.bsize, self.lnum, self.addr_size)
        write_line=self.line[index]
        write_line.write(tag, offset, data)
        pass




if __name__=='__main__':
    c=cache(32, 2, 512, 32)
    print c.read(0x12345678)
    print c
    print c.write(0x12345678, 0xbb)
    print c
