import os, struct
def _dec(b):
    try: return b.decode('utf-8')
    except UnicodeDecodeError: return b.decode('latin1')
def load_tbl(path):
    d=open(path,'rb').read()
    crc,num,hsz=struct.unpack_from('<HHI',d,0)
    ver,fstart,maxtries,fend=struct.unpack_from('<BIII',d,8)
    idx=struct.unpack_from('<%dH'%num,d,21)
    hoff=21+num*2; out={}
    for i in range(num):
        u,ix,h,ko,so,sl=struct.unpack_from('<BHIIIH',d,hoff+idx[i]*17)
        if not u: continue
        k=_dec(d[ko:d.index(0,ko)]); s=_dec(d[so:d.index(0,so)])
        out[i]=(k,s)
    return out
def all_strings(folder='data'):
    # index offsets as in D2: string.tbl 0.., patchstring 10000.., expansion 20000.. ; folder = dossier data/
    t={}
    for f,base in [('string',0),('patchstring',10000),('expansionstring',20000)]:
        for i,v in load_tbl(os.path.join(folder, f + '.tbl')).items(): t[base+i]=v
    return t
