import struct, zlib, bz2, mmap
def _ct():
    t=[0]*0x500; seed=0x00100001
    for i in range(0x100):
        idx=i
        for j in range(5):
            seed=(seed*125+3)%0x2AAAAB; a=(seed&0xFFFF)<<16
            seed=(seed*125+3)%0x2AAAAB; b=seed&0xFFFF
            t[idx]=a|b; idx+=0x100
    return t
CT=_ct()
def hs(s,ht):
    s1=0x7FED7FED; s2=0xEEEEEEEE
    for c in s.upper().replace('/','\\'):
        c=ord(c); s1=(CT[(ht<<8)+c]^(s1+s2))&0xFFFFFFFF; s2=(c+s1+s2+(s2<<5)+3)&0xFFFFFFFF
    return s1
def decrypt(data,key):
    s2=0xEEEEEEEE; out=bytearray(); n=len(data)//4
    for i in range(n):
        s2=(s2+CT[0x400+(key&0xFF)])&0xFFFFFFFF
        v=struct.unpack_from('<I',data,i*4)[0]
        v=(v^(key+s2))&0xFFFFFFFF
        key=(((~key<<0x15)+0x11111111)|(key>>0x0B))&0xFFFFFFFF
        s2=(v+s2+(s2<<5)+3)&0xFFFFFFFF
        out+=struct.pack('<I',v)
    return bytes(out)+data[n*4:]

# PKWARE DCL explode
def explode(src):
    class BR:
        def __init__(s,d): s.d=d; s.p=0; s.bit=0
        def bits(s,n):
            v=0
            for i in range(n):
                byte=s.d[s.p]; v|=((byte>>s.bit)&1)<<i
                s.bit+=1
                if s.bit==8: s.bit=0; s.p+=1
            return v
    ctype=src[0]; dsize=src[1]
    br=BR(src[2:])
    LenBits=[3,2,3,3,4,4,4,5,5,5,5,6,6,6,7,7]
    LenCode=[5,3,1,6,10,2,12,20,4,24,8,48,16,32,64,0]
    ExLenBits=[0,0,0,0,0,0,0,0,1,2,3,4,5,6,7,8]
    LenBase=[0,1,2,3,4,5,6,7,8,10,14,22,38,70,134,262]
    DistBits=[2,4,4,5,5,5,5,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8]
    DistCode=[0x03,0x0D,0x05,0x19,0x09,0x11,0x01,0x3E,0x1E,0x2E,0x0E,0x36,0x16,0x26,0x06,0x3A,0x1A,0x2A,0x0A,0x32,0x12,0x22,0x42,0x02,0x7C,0x3C,0x5C,0x1C,0x6C,0x2C,0x4C,0x0C,0x74,0x34,0x54,0x14,0x64,0x24,0x44,0x04,0x78,0x38,0x58,0x18,0x68,0x28,0x48,0x08,0xF0,0x70,0xB0,0x30,0xD0,0x50,0x90,0x10,0xE0,0x60,0xA0,0x20,0xC0,0x40,0x80,0x00]
    def build(bits,codes):
        m={}
        for i,(b,c) in enumerate(zip(bits,codes)): m[(b,c)]=i
        return m
    lenmap=build(LenBits,LenCode); distmap=build(DistBits,DistCode)
    def decode(m,maxb):
        v=0
        for n in range(1,maxb+1):
            v|=br.bits(1)<<(n-1)
            if (n,v) in m: return m[(n,v)]
        raise ValueError('bad code')
    if ctype!=0: raise NotImplementedError('ascii mode')
    out=bytearray()
    while True:
        if br.bits(1)==0:
            out.append(br.bits(8))
        else:
            li=decode(lenmap,7)
            ln=LenBase[li]+br.bits(ExLenBits[li])
            if ln==517: break
            ln+=2
            di=decode(distmap,8)
            if ln==2: dist=(di<<2)|br.bits(2)
            else: dist=(di<<dsize)|br.bits(dsize)
            dist+=1
            for k in range(ln): out.append(out[-dist])
    return bytes(out)

def decompress(d):
    t=d[0]; d=d[1:]
    if t==2: return zlib.decompress(d)
    if t==0x10: return bz2.decompress(d)
    if t==8: return explode(d)
    raise NotImplementedError(hex(t))

class MPQ:
    def __init__(s,path):
        with open(path,'rb') as fh:   # mmap : les MPQ du jeu font jusqu'à 350 Mo
            s.f=mmap.mmap(fh.fileno(),0,access=mmap.ACCESS_READ)
        m,hsz,asz,ver,shift,hto,bto,hn,bn=struct.unpack_from('<4sIIHHIIII',s.f,0)
        s.sector=512<<shift
        s.ht=decrypt(s.f[hto:hto+hn*16],hs('(hash table)',3))
        s.bt=decrypt(s.f[bto:bto+bn*16],hs('(block table)',3))
        s.hn=hn
        s.hashes=[struct.unpack_from('<IIHHI',s.ht,i*16) for i in range(hn)]
        s.blocks=[struct.unpack_from('<IIII',s.bt,i*16) for i in range(bn)]
    def find(s,name):
        a=hs(name,1); b=hs(name,2); i=hs(name,0)%s.hn
        for k in range(s.hn):
            h=s.hashes[(i+k)%s.hn]
            if h[4]==0xFFFFFFFF: return None
            if h[0]==a and h[1]==b and h[4]<len(s.blocks): return h[4]
        return None
    def read(s,name=None,bi=None,key=None):
        if bi is None: bi=s.find(name)
        if bi is None: return None
        off,csz,fsz,fl=s.blocks[bi]
        raw=s.f[off:off+csz]
        if key is None and fl&0x10000:
            base=name.replace('/','\\').split('\\')[-1]
            key=hs(base,3)
            if fl&0x20000: key=(key+off)^fsz
        if fl&0x01000000:  # single unit
            data=raw
            if key is not None and fl&0x10000: data=decrypt(data,key)
            return decompress(data) if (fl&0x200 and csz<fsz) else data[:fsz]
        if not fl&0x700:
            return decrypt(raw,key)[:fsz] if fl&0x10000 else raw[:fsz]
        ns=(fsz+s.sector-1)//s.sector
        tbl=raw[:(ns+1)*4]
        if fl&0x10000: tbl=decrypt(tbl,(key-1)&0xFFFFFFFF)
        offs=struct.unpack('<%dI'%(ns+1),tbl)
        out=b''
        for i in range(ns):
            chunk=raw[offs[i]:offs[i+1]]
            if fl&0x10000: chunk=decrypt(chunk,(key+i)&0xFFFFFFFF)
            exp=min(s.sector,fsz-i*s.sector)
            if len(chunk)<exp:
                chunk=decompress(chunk) if fl&0x200 else explode(chunk)
            out+=chunk
        return out
