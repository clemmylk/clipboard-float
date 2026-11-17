"""Local, memory-only clipboard history. No network or keystroke storage."""
import ctypes as C
from ctypes import wintypes as W
import os,sys,time,queue,threading,hashlib,subprocess
from pathlib import Path

U=C.WinDLL('user32',use_last_error=True);K=C.WinDLL('kernel32',use_last_error=True)
PTR=C.c_size_t;LRESULT=C.c_ssize_t
K.GlobalLock.argtypes=[W.HGLOBAL];K.GlobalLock.restype=C.c_void_p
K.GlobalUnlock.argtypes=[W.HGLOBAL]
K.GlobalSize.argtypes=[W.HGLOBAL];K.GlobalSize.restype=PTR
K.GlobalAlloc.argtypes=[W.UINT,PTR];K.GlobalAlloc.restype=W.HGLOBAL
K.GlobalFree.argtypes=[W.HGLOBAL];K.GlobalFree.restype=W.HGLOBAL
U.GetClipboardData.argtypes=[W.UINT];U.GetClipboardData.restype=W.HANDLE
U.SetClipboardData.argtypes=[W.UINT,W.HANDLE];U.SetClipboardData.restype=W.HANDLE
U.OpenClipboard.argtypes=[W.HWND];U.OpenClipboard.restype=W.BOOL
U.GetParent.argtypes=[W.HWND];U.GetParent.restype=W.HWND
U.GetForegroundWindow.restype=W.HWND
U.SetForegroundWindow.argtypes=[W.HWND]
U.IsWindow.argtypes=[W.HWND]
K.CreateMutexW.argtypes=[C.c_void_p,W.BOOL,W.LPCWSTR];K.CreateMutexW.restype=W.HANDLE
K.CreateEventW.argtypes=[C.c_void_p,W.BOOL,W.BOOL,W.LPCWSTR];K.CreateEventW.restype=W.HANDLE
K.SetEvent.argtypes=[W.HANDLE];K.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD]
U.RegisterClipboardFormatW.argtypes=[W.LPCWSTR];U.RegisterClipboardFormatW.restype=W.UINT
U.CallNextHookEx.argtypes=[W.HANDLE,C.c_int,W.WPARAM,W.LPARAM];U.CallNextHookEx.restype=LRESULT
U.SetWindowsHookExW.restype=W.HANDLE
U.UnhookWindowsHookEx.argtypes=[W.HANDLE]
K.GetModuleHandleW.argtypes=[W.LPCWSTR];K.GetModuleHandleW.restype=W.HMODULE
U.PostThreadMessageW.argtypes=[W.DWORD,W.UINT,W.WPARAM,W.LPARAM]
CF_TEXT=13;CF_DIB=8;CF_FILES=15
EVENT='Local\\ClipboardHistoryPopup_v1';MUTEX='Local\\ClipboardHistoryRunning_v1'

class KBD(C.Structure):
 _fields_=[('vkCode',W.DWORD),('scanCode',W.DWORD),('flags',W.DWORD),('time',W.DWORD),('extra',PTR)]
class KEY(C.Structure):
 _fields_=[('vk',W.WORD),('scan',W.WORD),('flags',W.DWORD),('time',W.DWORD),('extra',PTR)]
class MOUSE(C.Structure):
 _fields_=[('dx',W.LONG),('dy',W.LONG),('data',W.DWORD),('flags',W.DWORD),('time',W.DWORD),('extra',PTR)]
class INPUTUNION(C.Union):_fields_=[('ki',KEY),('mi',MOUSE)]
class INPUT(C.Structure):_anonymous_=('u',);_fields_=[('kind',W.DWORD),('u',INPUTUNION)]
U.SendInput.argtypes=[W.UINT,C.POINTER(INPUT),C.c_int];U.SendInput.restype=W.UINT
HOOK=C.WINFUNCTYPE(LRESULT,C.c_int,W.WPARAM,W.LPARAM)

class Store:
 def __init__(self):self.items=[];self.serial=0
 def add(self,formats,label,kind,digest=None):
  if digest is None:
   hasher=hashlib.sha256()
   for f in sorted(formats):hasher.update(str(f).encode());hasher.update(formats[f])
   digest=hasher.hexdigest()
  existing=next((i for i in self.items if i['digest']==digest),None)
  if existing:self.items.remove(existing)
  else:
   self.serial+=1;existing={'id':str(self.serial),'formats':formats,'label':label,'kind':kind,'digest':digest}
  existing['when']=time.time();self.items.insert(0,existing)
  while len(self.items)>40 or sum(sum(len(v) for v in i['formats'].values()) for i in self.items)>64*1024*1024:self.items.pop()
  return existing

def clipboard_read():
 if not U.OpenClipboard(None):return None
 try:
  for name in ('ExcludeClipboardContentFromMonitorProcessing','CanIncludeInClipboardHistory'):
   f=U.RegisterClipboardFormatW(name)
   if U.IsClipboardFormatAvailable(f):
    if name.startswith('Exclude'):return {}
    h=U.GetClipboardData(f);ptr=K.GlobalLock(h) if h else None
    if ptr:
     try:
      if K.GlobalSize(h)>=4 and C.c_uint32.from_address(ptr).value==0:return {}
     finally:K.GlobalUnlock(h)
  formats={};label='';kind='Text'
  for fmt in (CF_TEXT,CF_DIB,CF_FILES):
   if not U.IsClipboardFormatAvailable(fmt):continue
   h=U.GetClipboardData(fmt)
   if not h:continue
   size=K.GlobalSize(h)
   if not size or size>12*1024*1024:continue
   ptr=K.GlobalLock(h)
   if not ptr:continue
   try:raw=C.string_at(ptr,size)
   finally:K.GlobalUnlock(h)
   if fmt==CF_TEXT:
    label=raw.decode('utf-16-le',errors='replace').split('\0',1)[0]
    if not label:continue
   if fmt==CF_DIB:
    kind='Image'
    if size>=12:
     width=C.c_int32.from_buffer_copy(raw[4:8]).value;height=abs(C.c_int32.from_buffer_copy(raw[8:12]).value)
     label=f'Image   {width} x {height} pixels'
   if fmt==CF_FILES:
    kind='Files'
    if size>=20:
     offset=int.from_bytes(raw[:4],'little');wide=int.from_bytes(raw[16:20],'little')
     names=raw[offset:].decode('utf-16-le' if wide else 'mbcs',errors='replace').rstrip('\0').split('\0')
     label='\n'.join(names)
   formats[fmt]=raw
  return (formats,label,kind) if formats else {}
 finally:U.CloseClipboard()

def clipboard_write(item,owner=None):
 if not U.OpenClipboard(owner):return False
 try:
  U.EmptyClipboard()
  for fmt,raw in item['formats'].items():
   h=K.GlobalAlloc(0x42,len(raw));ptr=K.GlobalLock(h) if h else None
   if not ptr:
    if h:K.GlobalFree(h)
    return False
   C.memmove(ptr,raw,len(raw));K.GlobalUnlock(h)
   if not U.SetClipboardData(fmt,h):K.GlobalFree(h);return False
  return True
 finally:U.CloseClipboard()

def paste_keys():
 events=(INPUT*4)()
 for event,(key,flags) in zip(events,[(0x11,0),(0x56,0),(0x56,2),(0x11,2)]):event.kind=1;event.ki=KEY(key,0,flags,0,0)
 return U.SendInput(4,events,C.sizeof(INPUT))==4

class Hotkeys:
 def __init__(self,commands):self.commands=commands;self.stop=False;self.thread_id=0;self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
 def run(self):
  self.thread_id=K.GetCurrentThreadId();tab=False;suppress=False
  @HOOK
  def callback(code,msg,data):
   nonlocal tab,suppress
   if code>=0:
    event=C.cast(data,C.POINTER(KBD)).contents;down=msg in (0x100,0x104);up=msg in (0x101,0x105)
    if event.vkCode==9:
     if down:tab=True
     if up:tab=False
    if event.vkCode==0x56:
     if down and tab:
      if not suppress:self.commands.put(('show',U.GetForegroundWindow()))
      suppress=True;return 1
     if up and suppress:suppress=False;return 1
   return U.CallNextHookEx(None,code,msg,data)
  self.callback=callback
  U.SetWindowsHookExW.argtypes=[C.c_int,HOOK,W.HMODULE,W.DWORD]
  self.hook=U.SetWindowsHookExW(13,callback,K.GetModuleHandleW(None),0)
  U.RegisterHotKey(None,1,0x4000|0x2|0x1,0x56)
  if not self.hook:self.commands.put(('error','Tab + V could not be registered. Try Ctrl + Alt + V.'))
  message=W.MSG()
  while U.GetMessageW(C.byref(message),None,0,0)>0:
   if message.message==0x312:self.commands.put(('show',U.GetForegroundWindow()))
   U.TranslateMessage(C.byref(message));U.DispatchMessageW(C.byref(message))
  U.UnregisterHotKey(None,1)
  if self.hook:U.UnhookWindowsHookEx(self.hook)
 def close(self):
  if self.thread_id:U.PostThreadMessageW(self.thread_id,0x12,0,0)

