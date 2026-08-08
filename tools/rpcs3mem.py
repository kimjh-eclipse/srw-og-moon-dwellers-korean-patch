#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RPCS3 프로세스 메모리 어태치/스캔 도구 (Win32 ReadProcessMemory).
GUI 조작 없이, 실행 중인 RPCS3의 게스트 메모리를 읽고 시그니처를 검색한다.
사용 예:
  python rpcs3mem.py find <hex_or_ascii_pattern>   # 패턴 검색
  python rpcs3mem.py base                          # FTTF/게스트맵 추정
"""
import ctypes, ctypes.wintypes as w, sys, io
k=ctypes.windll.kernel32

class PE(ctypes.Structure):
    _fields_=[('dwSize',w.DWORD),('cntUsage',w.DWORD),('th32ProcessID',w.DWORD),
    ('th32DefaultHeapID',ctypes.POINTER(ctypes.c_ulong)),('th32ModuleID',w.DWORD),
    ('cntThreads',w.DWORD),('th32ParentProcessID',w.DWORD),('pcPriClassBase',ctypes.c_long),
    ('dwFlags',w.DWORD),('szExeFile',ctypes.c_char*260)]
class MBI(ctypes.Structure):
    _fields_=[('BaseAddress',ctypes.c_void_p),('AllocationBase',ctypes.c_void_p),
    ('AllocationProtect',w.DWORD),('RegionSize',ctypes.c_size_t),('State',w.DWORD),
    ('Protect',w.DWORD),('Type',w.DWORD)]

def find_pid():
    snap=k.CreateToolhelp32Snapshot(0x2,0); pe=PE(); pe.dwSize=ctypes.sizeof(PE)
    pid=None
    if k.Process32First(snap,ctypes.byref(pe)):
        while True:
            if 'rpcs3' in pe.szExeFile.decode('latin-1').lower(): pid=pe.th32ProcessID; break
            if not k.Process32Next(snap,ctypes.byref(pe)): break
    k.CloseHandle(snap); return pid

def open_proc(pid):
    h=k.OpenProcess(0x10|0x400,False,pid)   # VM_READ|QUERY_INFORMATION
    if not h: raise OSError('OpenProcess 실패(권한). 관리자 권한 필요할 수 있음')
    return h

def regions(h, min_size=0x1000):
    addr=0; out=[]; mbi=MBI()
    while addr < 0x7FFFFFFFFFFF:
        if not k.VirtualQueryEx(h,ctypes.c_void_p(addr),ctypes.byref(mbi),ctypes.sizeof(mbi)):
            addr+=0x1000; continue
        base=mbi.BaseAddress or 0; size=mbi.RegionSize or 0x1000
        # MEM_COMMIT & 읽기가능
        if mbi.State==0x1000 and (mbi.Protect & 0xEE) and mbi.RegionSize>=min_size:
            out.append((base,size,mbi.Protect))
        addr=base+size
    return out

def read(h, addr, size):
    buf=ctypes.create_string_buffer(size); got=ctypes.c_size_t(0)
    if not k.ReadProcessMemory(h,ctypes.c_void_p(addr),buf,size,ctypes.byref(got)):
        return b''
    return buf.raw[:got.value]

def search(h, pattern, limit=50, min_region=0x100000):
    hits=[]
    for base,size,prot in regions(h, min_region):
        off=0; CH=0x400000
        while off<size:
            chunk=read(h, base+off, min(CH,size-off))
            if not chunk: break
            i=chunk.find(pattern)
            while i!=-1:
                hits.append(base+off+i)
                if len(hits)>=limit: return hits
                i=chunk.find(pattern,i+1)
            off+=len(chunk) if chunk else CH
    return hits

if __name__=='__main__':
    pid=find_pid()
    if not pid: print('RPCS3 미실행'); sys.exit(1)
    print('RPCS3 PID',pid); h=open_proc(pid)
    cmd=sys.argv[1] if len(sys.argv)>1 else 'base'
    if cmd=='find':
        p=sys.argv[2]
        pat=bytes.fromhex(p) if all(c in '0123456789abcdefABCDEF' for c in p) and len(p)%2==0 else p.encode('utf-8')
        print('패턴',pat[:32]); hits=search(h,pat)
        for a in hits[:50]: print(f'  hit @ {a:#x}')
        print('총',len(hits))
    elif cmd=='base':
        hits=search(h,b'FTTF',20)
        print('FTTF 시그니처 위치:',[hex(a) for a in hits])
        big=sorted(regions(h,0x8000000),key=lambda x:-x[1])[:8]
        print('대형 커밋영역:')
        for b,s,p in big: print(f'  {b:#x} {s/1024/1024:.0f}MB prot={p:#x}')
    k.CloseHandle(h)
