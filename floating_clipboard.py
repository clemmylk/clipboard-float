"""Clipboard Float: antialiased, spring-animated native radial clipboard menu."""
import sys,os,time,math,queue,struct,subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import Qt,QTimer,QRectF,QPointF,QEvent,QObject,Signal,QAbstractNativeEventFilter
from PySide6.QtGui import QColor,QPainter,QPainterPath,QPainterPathStroker,QPen,QFont,QCursor,QRegion,QImage,QPixmap,QIcon,QAction
from PySide6.QtWidgets import QApplication,QWidget,QLineEdit,QMenu,QSystemTrayIcon
import clipboard_backend as backend
from filee_motion import Spring,point_at,angle_of,index_at,ACCENT,PAGE,SURFACE,ALT,TEXT,MUTED

SIZE=580;CX=CY=290;OUTER=230;INNER=104;COUNT=6

def color(hex,alpha=None):
 c=QColor(hex)
 if alpha is not None:c.setAlpha(alpha)
 return c

def mix(a,b,t):
 a=QColor(a);b=QColor(b);t=max(0,min(1,t));return QColor.fromRgbF(a.redF()+(b.redF()-a.redF())*t,a.greenF()+(b.greenF()-a.greenF())*t,a.blueF()+(b.blueF()-a.blueF())*t)

def wedge(cx,cy,inner,outer,mid,span=math.tau/6,gap=7):
 # Constant-width gap, ported from Filee DonutGeometry.Wedge.
 inner+=6;outer-=6;gap+=12
 oh=max(.001,span/2-gap/2/outer);ih=max(.001,span/2-gap/2/inner)
 path=QPainterPath();x,y=point_at(cx,cy,outer,mid-oh);path.moveTo(x,y)
 rect=QRectF(cx-outer,cy-outer,outer*2,outer*2)
 path.arcTo(rect,90-math.degrees(mid-oh),-math.degrees(2*oh))
 x,y=point_at(cx,cy,inner,mid+ih);path.lineTo(x,y)
 path.arcTo(QRectF(cx-inner,cy-inner,inner*2,inner*2),90-math.degrees(mid+ih),math.degrees(2*ih));path.closeSubpath()
 stroke=QPainterPathStroker();stroke.setWidth(12);stroke.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
 return path.united(stroke.createStroke(path)).simplified()

def image_of(item):
 raw=item.get('formats',{}).get(backend.CF_DIB)
 if not raw or len(raw)<40:return QImage()
 try:
  header=int.from_bytes(raw[:4],'little');bpp=int.from_bytes(raw[14:16],'little');compression=int.from_bytes(raw[16:20],'little');used=int.from_bytes(raw[32:36],'little')
  palette=(used or (1<<bpp))*4 if bpp<=8 else 0;extra=12 if header==40 and compression==3 else 0
  bmp=b'BM'+struct.pack('<IHHI',14+len(raw),0,0,14+header+palette+extra)+raw
  return QImage.fromData(bmp,'BMP')
 except (ValueError,OverflowError,struct.error):return QImage()

class FloatMenu(QWidget):
 def __init__(self,controller):
  super().__init__(None,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint)
  self.controller=controller;self.setWindowTitle('Clipboard Float');self.setAccessibleName('Floating clipboard history');self.setAccessibleDescription('Six recent clipboard entries around a circular preview. Up and Down select. Enter pastes. Ctrl Enter copies. Scroll or Page Down shows older entries. Escape closes.');self.setFixedSize(SIZE,SIZE);self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground);self.setMouseTracking(True);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
  self.opening=Spring();self.hover=[Spring() for _ in range(COUNT)];self.hovered=-1;self.selected=0;self.page=0;self.closing=False;self.after_close=None;self.last=time.perf_counter();self.preview_cache={};self.drag_at=None;self.fonts={};self.sprites={};self.hub_cache=None;self.filter_cache=(None,[]);self.render_cache_key=None;self.footer_cache=None;self.paths=[wedge(CX,CY,INNER,OUTER,i*math.tau/COUNT) for i in range(COUNT)]
  self.search=QLineEdit(self);self.search.setGeometry(125,10,330,42);self.search.setPlaceholderText('Search clipboard…');self.search.setAccessibleName('Search clipboard history');self.search.setStyleSheet('QLineEdit{background:#F6F5F1;color:#1F1E1D;border:1px solid #DDDAD0;border-radius:20px;padding:0 18px;font:12px "Segoe UI";}QLineEdit:focus{border:1px solid #7F77DD;}');self.search.textChanged.connect(self.filter_changed);self.search.installEventFilter(self)
  self.timer=QTimer(self);self.timer.setTimerType(Qt.TimerType.PreciseTimer);self.timer.setInterval(16);self.timer.timeout.connect(self.frame)
  self._mask();self.hide()
 def _mask(self):
  region=QRegion(CX-OUTER-15,CY-OUTER-15,(OUTER+15)*2,(OUTER+15)*2,QRegion.RegionType.Ellipse)
  region=region.united(QRegion(120,5,340,50));region=region.united(QRegion(95,535,390,45));self.setMask(region)
 def all_items(self):
  key=(self.search.text().casefold(),tuple((i['id'],i['when']) for i in self.controller.store.items))
  if self.filter_cache[0]!=key:
   q=key[0];self.filter_cache=(key,[i for i in self.controller.store.items if not q or q in i['label'].casefold()])
  return self.filter_cache[1]
 def entries(self):return self.all_items()[self.page*COUNT:(self.page+1)*COUNT]
 def filter_changed(self):self.page=0;self.selected=0;self.hovered=-1;self.update()
 def wake(self):
  self.last=time.perf_counter()
  if not self.timer.isActive():self.timer.start()
 def reveal(self,target=None):
  if target and target!=int(self.winId()):self.controller.target=target
  self.page=0;self.selected=0;self.hovered=-1;self.search.clear();self.was_active=False;self.closing=False;self.after_close=None;self.opening=Spring(.78);self.hover=[Spring() for _ in range(COUNT)]
  cursor=QCursor.pos();screen=QApplication.screenAt(cursor) or QApplication.primaryScreen();bounds=screen.availableGeometry()
  x=max(bounds.left()+6,min(cursor.x()-CX,bounds.right()-SIZE-6));y=max(bounds.top()+6,min(cursor.y()-CY,bounds.bottom()-SIZE-6));self.move(x,y)
  self.show();self.raise_();self.activateWindow();self.search.setFocus();self.wake()
 def dismiss(self,done=None):
  if self.closing:
   if done is not None:self.after_close=done
   return
  if not self.isVisible():
   if done:done()
   return
  self.closing=True;self.closing_at=time.perf_counter();self.after_close=done;self.wake()
 def frame(self):
  now=time.perf_counter();dt=min(.05,now-self.last);self.last=now
  active=self.opening.step(0 if self.closing else 1,dt,400,36 if self.closing else 24)
  for i,h in enumerate(self.hover):active=h.step(1 if i==self.hovered and not self.closing else 0,dt) or active
  self.update()
  if self.closing and (self.opening.value<.015 or now-self.closing_at>=.10):
   self.hide();self.timer.stop();done=self.after_close;self.after_close=None;self.closing=False
   if done:done()
  elif not active:self.timer.stop()
 def font(self,size=11,bold=False):
  key=(size,bold)
  if key not in self.fonts:self.fonts[key]=QFont('Segoe UI',size,QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
  return self.fonts[key]
 def text(self,p,rect,text,size=10,ink=TEXT,bold=False,flags=Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap):
  p.setFont(self.font(size,bold));p.setPen(color(ink));p.drawText(rect,flags,text)
 def icon(self,p,x,y,kind,scale=1,ink=ACCENT):
  p.save();p.translate(x,y);p.scale(scale,scale);p.setPen(QPen(color(ink),1.7,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin));p.setBrush(Qt.BrushStyle.NoBrush)
  if kind=='Image':
   p.drawRoundedRect(QRectF(-11,-9,22,18),4,4);p.drawEllipse(QPointF(4,-3),2,2);path=QPainterPath(QPointF(-8,6));path.lineTo(-2,0);path.lineTo(2,4);path.lineTo(6,0);path.lineTo(9,5);p.drawPath(path)
  elif kind=='Files':
   path=QPainterPath();path.moveTo(-11,-6);path.lineTo(-3,-6);path.lineTo(0,-9);path.lineTo(10,-9);path.lineTo(10,9);path.lineTo(-11,9);path.closeSubpath();p.drawPath(path)
  elif kind=='search':p.drawEllipse(QPointF(-2,-2),7,7);p.drawLine(QPointF(3,3),QPointF(9,9))
  elif kind=='copy':p.drawRoundedRect(QRectF(-5,-6,13,16),3,3);p.drawLine(QPointF(-9,5),QPointF(-9,-10));p.drawLine(QPointF(-9,-10),QPointF(3,-10))
  else:
   p.drawRoundedRect(QRectF(-10,-11,20,22),4,4)
   for yy,w in [(-5,12),(0,12),(5,8)]:p.drawLine(QPointF(-6,yy),QPointF(-6+w,yy))
  p.restore()
 def layer(self,rect,draw):
  dpr=self.devicePixelRatioF();pix=QPixmap(math.ceil(rect.width()*dpr),math.ceil(rect.height()*dpr));pix.setDevicePixelRatio(dpr);pix.fill(Qt.GlobalColor.transparent)
  p=QPainter(pix);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform);p.translate(-rect.x(),-rect.y());draw(p);p.end();return pix,rect.topLeft()
 def slice_sprite(self,i,item,lit):
  key=(i,item['digest'] if item else None,item['when'] if item else None,lit)
  if key in self.sprites:return self.sprites[key]
  path=self.paths[i];rect=path.boundingRect().adjusted(-7,-7,7,13);mid=i*math.tau/COUNT
  def draw(p):
   p.save();p.translate(0,6);p.setPen(QPen(color('#000000',5),10));p.setBrush(color('#000000',9));p.drawPath(path);p.restore()
   p.setPen(QPen(color(ACCENT if lit else '#E4E1DA'),1));p.setBrush(color('#E4E0FF' if lit else SURFACE) if item else color('#EFEDE6',195));p.drawPath(path)
   x,y=point_at(CX,CY,(INNER+OUTER)/2,mid)
   if item:
    self.icon(p,x,y-23,item['kind'],1,ACCENT)
    label=' '.join(item['label'][:512].split());label=label[:27]+'…' if len(label)>28 else label
    self.text(p,QRectF(x-57,y-5,114,43),label,9,TEXT,True)
    self.text(p,QRectF(x-50,y+39,100,16),str(i+1)+'  ·  '+self.age(item),8,MUTED)
   else:self.text(p,QRectF(x-40,y-12,80,24),'—',15,'#CBC7BD')
  result=self.layer(rect,draw);self.sprites[key]=result;return result
 def hub_sprite(self,item):
  digest=item['digest'] if item else None;image=self.preview_cache.get(digest)
  key=(digest,self.age(item) if item else None,image is not None)
  if self.hub_cache and self.hub_cache[0]==key:return self.hub_cache[1]
  def draw(p):
   p.setPen(QPen(color('#DEDAD1'),1));p.setBrush(color(PAGE));p.drawEllipse(QPointF(CX,CY),INNER-8,INNER-8)
   if item:
    if item['kind']=='Image' and image is None and hasattr(self.controller,'request_preview'):self.controller.request_preview(item)
    if item['kind']=='Image' and image is not None and not image.isNull():
     w=image.width()/2;h=image.height()/2;p.drawImage(QRectF(CX-w/2,CY-50,w,h),image)
     self.text(p,QRectF(CX-78,CY+58,156,20),'IMAGE  ·  CLICK TO PASTE',7,MUTED,True)
    else:self.hub_text(p,item)
   else:
    self.icon(p,CX,CY-31,'copy',1.3);self.text(p,QRectF(CX-80,CY-8,160,30),'Clipboard',16,TEXT,True);self.text(p,QRectF(CX-80,CY+29,160,43),'Copy something.\nIt will appear here.',9,MUTED)
  result=self.layer(QRectF(CX-INNER,CY-INNER,INNER*2,INNER*2),draw);self.hub_cache=(key,result);return result
 def footer_sprite(self,total):
  key=(self.page,total)
  if self.footer_cache and self.footer_cache[0]==key:return self.footer_cache[1]
  def draw(p):
   self.pill(p,QRectF(106,537,368,36));self.text(p,QRectF(114,541,40,28),'‹',20,MUTED)
   pages=max(1,math.ceil(total/COUNT));self.text(p,QRectF(157,541,192,28),f'{self.page+1} / {pages}     ·     {total} clips',9,MUTED,True)
   self.text(p,QRectF(347,541,40,28),'›',20,MUTED);self.text(p,QRectF(393,540,61,28),'•••',13,MUTED)
  result=self.layer(QRectF(105,536,370,39),draw);self.footer_cache=(key,result);return result
 def paintEvent(self,event):
  p=QPainter(self);p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
  v=max(0,self.opening.value)
  if self.closing:v=max(0,1-(time.perf_counter()-self.closing_at)/.10)**2
  opacity=min(1,v*1.8);p.setOpacity(opacity);p.translate(CX,CY);p.scale(.78+.22*v,.78+.22*v);p.rotate(-7*(1-min(1,v)));p.translate(-CX,-CY)
  entries=self.entries();count=len(entries);pagekey=(self.page,tuple((i['digest'],i['when']) for i in entries),int(time.time()//60),self.devicePixelRatioF())
  if self.render_cache_key!=pagekey:self.sprites.clear();self.render_cache_key=pagekey;self.hub_cache=None;self.footer_cache=None
  for i in range(COUNT):
   mid=i*math.tau/COUNT;h=max(0,min(1,self.hover[i].value));item=entries[i] if i<count else None
   base,pos=self.slice_sprite(i,item,False);offset=QPointF(math.sin(mid)*7*h,-math.cos(mid)*7*h)
   p.drawPixmap(pos+offset,base)
   if h>.001 and item:
    lit,_=self.slice_sprite(i,item,True);p.setOpacity(opacity*h);p.drawPixmap(pos+offset,lit);p.setOpacity(opacity)
  idx=self.hovered if self.hovered>=0 else self.selected;item=entries[idx] if 0<=idx<count else None
  pix,pos=self.hub_sprite(item);p.drawPixmap(pos,pix)
  p.resetTransform();pix,pos=self.footer_sprite(len(self.all_items()));p.drawPixmap(pos,pix);p.end()
 def hub_text(self,p,item):
  self.text(p,QRectF(CX-75,CY-66,150,20),item['kind'].upper()+'  ·  '+self.age(item),8,ACCENT,True)
  label=item['label'];label=label[:110]+'…' if len(label)>110 else label
  self.text(p,QRectF(CX-76,CY-39,152,92),label,10,TEXT,True)
  self.text(p,QRectF(CX-77,CY+61,154,20),'CLICK OR ENTER TO PASTE',7,MUTED,True)
 def pill(self,p,rect):p.setPen(QPen(color('#DEDAD1'),1));p.setBrush(color(PAGE));p.drawRoundedRect(rect,18,18)
 def age(self,item):
  age=max(0,int(time.time()-item['when']));return 'just now' if age<60 else (f'{age//60}m ago' if age<3600 else f'{age//3600}h ago')
 def hit(self,pos):
  dx=pos.x()-CX;dy=pos.y()-CY;radius=math.hypot(dx,dy)
  if INNER<=radius<=OUTER+12:return index_at(angle_of(CX,CY,pos.x(),pos.y()),COUNT)
  return -1
 def mouseMoveEvent(self,event):
  if self.drag_at is not None:
   self.move(event.globalPosition().toPoint()-self.drag_at);return
  hit=self.hit(event.position())
  if hit>=len(self.entries()):hit=-1
  if hit!=self.hovered:
   self.hovered=hit
   if hit>=0:self.selected=hit
   self.wake()
  self.setCursor(Qt.CursorShape.PointingHandCursor if hit>=0 else Qt.CursorShape.ArrowCursor)
 def leaveEvent(self,event):self.hovered=-1;self.wake()
 def mousePressEvent(self,event):
  pos=event.position();i=self.hit(pos)
  if i>=0 and i<len(self.entries()):self.activate(i,event.button()!=Qt.MouseButton.RightButton);return
  if 537<=pos.y()<=578:
   if pos.x()<157:self.change_page(-1)
   elif pos.x()<347:self.search.setFocus();self.search.selectAll()
   elif pos.x()<393:self.change_page(1)
   else:self.controller.menu(self.mapToGlobal(pos.toPoint()))
  elif math.hypot(pos.x()-CX,pos.y()-CY)<INNER:
   if event.button()==Qt.MouseButton.RightButton:self.controller.menu(event.globalPosition().toPoint())
   elif event.button()==Qt.MouseButton.MiddleButton:self.drag_at=event.globalPosition().toPoint()-self.pos()
   else:self.activate(self.selected)
  else:self.dismiss()
 def mouseReleaseEvent(self,event):self.drag_at=None
 def wheelEvent(self,event):self.change_page(-1 if event.angleDelta().y()>0 else 1)
 def change_page(self,delta):
  pages=max(1,math.ceil(len(self.all_items())/COUNT));self.page=(self.page+delta)%pages;self.hovered=-1;self.selected=0;self.hover=[Spring() for _ in range(COUNT)];self.update()
 def activate(self,index,paste=True):
  entries=self.entries()
  if 0<=index<len(entries):self.controller.choose(entries[index],paste)
 def handle_key(self,event):
  key=event.key()
  if key in (Qt.Key.Key_Tab,Qt.Key.Key_Backtab) and not event.modifiers()&(Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.AltModifier):
   if not event.isAutoRepeat():self.change_page(-1 if key==Qt.Key.Key_Backtab or event.modifiers()&Qt.KeyboardModifier.ShiftModifier else 1)
   return True
  if key==Qt.Key.Key_Escape:self.dismiss();return True
  if key in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self.activate(self.selected,not bool(event.modifiers()&Qt.KeyboardModifier.ControlModifier));return True
  if key in (Qt.Key.Key_PageDown,Qt.Key.Key_PageUp):self.change_page(1 if key==Qt.Key.Key_PageDown else -1);return True
  if key in (Qt.Key.Key_Up,Qt.Key.Key_Down) and self.entries():
   self.selected=(self.selected+(1 if key==Qt.Key.Key_Down else -1))%len(self.entries());self.hovered=self.selected;self.wake();return True
  if event.modifiers()&Qt.KeyboardModifier.AltModifier and Qt.Key.Key_1<=key<=Qt.Key.Key_6:self.activate(key-Qt.Key.Key_1);return True
  return False
 def eventFilter(self,obj,event):
  if event.type()==QEvent.Type.KeyPress and self.handle_key(event):return True
  return super().eventFilter(obj,event)
 def keyPressEvent(self,event):
  if not self.handle_key(event):super().keyPressEvent(event)
 def closeEvent(self,event):event.ignore();self.dismiss()
 def event(self,event):
  if event.type()==QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Tab,Qt.Key.Key_Backtab) and self.handle_key(event):return True
  if event.type()==QEvent.Type.WindowActivate:self.was_active=True
  if event.type()==QEvent.Type.WindowDeactivate and getattr(self,'was_active',False) and self.isVisible() and not self.controller.context.isVisible():self.dismiss()
  return super().event(event)

class CommandBridge(QObject):
 ready=Signal(object)
 def put(self,command):self.ready.emit(command)

class ClipboardNotifications(QAbstractNativeEventFilter):
 def __init__(self,controller):super().__init__();self.controller=controller
 def nativeEventFilter(self,event_type,message):
  msg=backend.W.MSG.from_address(int(message))
  if msg.message==0x031D:self.controller.schedule_capture()
  return False

class Controller:
 def __init__(self,app,start_hidden=False):
  self.app=app;self.store=backend.Store();self.commands=CommandBridge();self.commands.ready.connect(self.handle_command,Qt.ConnectionType.QueuedConnection);self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='clipboard-reader');self.capture_busy=False;self.capture_retries=0;self.preview_pending=set();self.closed=False;self.target=None;self.paused=False;self.last_seq=None;self.event=backend.K.CreateEventW(None,False,False,backend.EVENT)
  self.window=FloatMenu(self);self.hotkeys=backend.Hotkeys(self.commands);self.timer=QTimer();self.timer.setInterval(1000);self.timer.timeout.connect(self.poll);self.timer.start()
  pix=QPixmap(32,32);pix.fill(Qt.GlobalColor.transparent);p=QPainter(pix);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setPen(QPen(color(ACCENT),7));p.drawEllipse(QRectF(7,7,18,18));p.end()
  self.tray=QSystemTrayIcon(QIcon(pix),app);self.tray.setToolTip('Clipboard Float · Tab + V');self.tray.activated.connect(self.tray_open);self.context=self.make_menu();self.tray.setContextMenu(self.context);self.tray.show()
  self.capture_timer=QTimer();self.capture_timer.setSingleShot(True);self.capture_timer.setInterval(20);self.capture_timer.timeout.connect(self.capture)
  self.native_filter=ClipboardNotifications(self);app.installNativeEventFilter(self.native_filter)
  backend.U.AddClipboardFormatListener.argtypes=[backend.W.HWND];backend.U.RemoveClipboardFormatListener.argtypes=[backend.W.HWND]
  self.listening=bool(backend.U.AddClipboardFormatListener(int(self.window.winId())))
  self.schedule_capture()
  if not start_hidden:QTimer.singleShot(400,lambda:self.window.reveal(backend.U.GetForegroundWindow()))
 def tray_open(self,reason):
  if reason==QSystemTrayIcon.ActivationReason.Trigger:self.window.reveal(backend.U.GetForegroundWindow())
 def startup_path(self):return Path(os.environ['APPDATA'])/'Microsoft'/'Windows'/'Start Menu'/'Programs'/'Startup'/'Clipboard History.lnk'
 def make_menu(self):
  menu=QMenu();menu.setStyleSheet('QMenu{background:#F6F5F1;color:#1F1E1D;border:1px solid #DDDAD0;border-radius:14px;padding:8px;font:12px "Segoe UI";}QMenu::item{padding:9px 22px;border-radius:7px;}QMenu::item:selected{background:#E4E0FF;}QMenu::separator{height:1px;background:#DEDAD1;margin:5px;}')
  menu.addAction('Open clipboard',lambda:self.window.reveal(backend.U.GetForegroundWindow()))
  self.pause_action=menu.addAction('Pause capture');self.pause_action.setCheckable(True);self.pause_action.triggered.connect(lambda checked:setattr(self,'paused',checked))
  startup=menu.addAction('Start with Windows');startup.setCheckable(True);startup.setChecked(self.startup_path().exists());startup.triggered.connect(self.toggle_startup)
  menu.addSeparator();menu.addAction('Clear history',self.clear);menu.addAction('About this menu',self.about);menu.addSeparator();menu.addAction('Quit',self.quit);return menu
 def menu(self,pos):self.context.popup(pos)
 def toggle_startup(self,enabled):
  if not enabled:self.startup_path().unlink(missing_ok=True);return
  env=os.environ.copy();env['CLIP_ROOT']=str(Path(__file__).resolve().parent);env['CLIP_SHORTCUT']=str(self.startup_path());env['CLIP_EXEC']=str(Path(sys.executable).with_name('pythonw.exe'))
  script=r'''$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:CLIP_SHORTCUT);$s.TargetPath=$env:CLIP_EXEC;$s.Arguments='"'+(Join-Path $env:CLIP_ROOT 'clipboard_history.py')+'" --background';$s.WorkingDirectory=$env:CLIP_ROOT;$s.Save()'''
  result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],env=env,creationflags=subprocess.CREATE_NO_WINDOW,capture_output=True)
  if result.returncode:self.tray.showMessage('Startup shortcut','Could not update the startup shortcut.')
 def clear(self):
  self.store.items.clear();self.window.preview_cache.clear();self.window.sprites.clear();self.window.filter_cache=(None,[]);self.window.hub_cache=None;self.window.footer_cache=None;self.window.render_cache_key=None;self.window.page=0;self.window.selected=0;self.window.update()
 def about(self):self.tray.showMessage('Clipboard Float','Filee-inspired radial UI. Adapted Filee geometry, springs and palette (MIT). Local, memory-only history. Tab+V / Ctrl+Alt+V.')
 def choose(self,item,paste):
  if not backend.clipboard_write(item,int(self.window.winId())):
   self.tray.showMessage('Clipboard busy','Please try again.');return
  self.last_seq=backend.U.GetClipboardSequenceNumber()
  target=self.target
  def done():
   if target and backend.U.IsWindow(target):
    success=backend.U.SetForegroundWindow(target)
    if paste and success:self.paste_when_released(target,time.perf_counter())
  self.window.dismiss(done)
 def paste_when_released(self,target,started):
  if backend.U.GetForegroundWindow()!=target:return
  if any(backend.U.GetAsyncKeyState(vk)&0x8000 for vk in (9,0x11,0x12,0x0D,0x56)):
   if time.perf_counter()-started<.5:QTimer.singleShot(12,lambda:self.paste_when_released(target,started))
   return
  backend.paste_keys()
 def handle_command(self,command):
  if self.closed:return
  action,value=command
  if action=='show':self.window.reveal(value)
  elif action=='captured':
   self.capture_busy=False;before,after,data=value
   if before!=after:self.schedule_capture();return
   if data is None:
    self.capture_retries+=1
    if self.capture_retries<12:self.capture_timer.start(50)
    return
   self.capture_retries=0;self.last_seq=after
   if data and not self.paused:
    self.store.add(*data);active={i['digest'] for i in self.store.items};self.window.preview_cache={k:v for k,v in self.window.preview_cache.items() if k in active};self.window.update()
    if data[2]=='Image':self.request_preview(self.store.items[0])
  elif action=='preview':
   digest,image=value;self.preview_pending.discard(digest)
   if any(i['digest']==digest for i in self.store.items):self.window.preview_cache[digest]=image;self.window.hub_cache=None;self.window.update()
  else:self.tray.showMessage('Clipboard Float',str(value))
 def schedule_capture(self):
  if not self.closed:self.capture_timer.start(15)
 def submit(self,kind,work):
  future=self.executor.submit(work)
  def finished(f):
   if self.closed:return
   try:self.commands.put((kind,f.result()))
   except (RuntimeError,OSError,ValueError):
    if kind=='captured':self.commands.put(('captured',(0,0,{})))
  future.add_done_callback(finished)
 def capture(self):
  if self.closed:return
  if self.capture_busy:self.capture_timer.start(30);return
  seq=backend.U.GetClipboardSequenceNumber()
  if self.paused:self.last_seq=seq;return
  if seq==self.last_seq:return
  self.capture_busy=True
  def read():
   before=backend.U.GetClipboardSequenceNumber();data=backend.clipboard_read();after=backend.U.GetClipboardSequenceNumber()
   if data:
    hasher=backend.hashlib.sha256()
    for fmt in sorted(data[0]):hasher.update(str(fmt).encode());hasher.update(data[0][fmt])
    data=(*data,hasher.hexdigest())
   return before,after,data
  self.submit('captured',read)
 def request_preview(self,item):
  digest=item['digest']
  if self.closed or digest in self.preview_pending or digest in self.window.preview_cache:return
  self.preview_pending.add(digest)
  def read():
   image=image_of(item)
   if not image.isNull():image=image.scaled(288,196,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
   return digest,image
  self.submit('preview',read)
 def poll(self):
  if backend.K.WaitForSingleObject(self.event,0)==0:self.window.reveal(backend.U.GetForegroundWindow())
  if not self.listening:self.schedule_capture()
 def quit(self):
  self.closed=True;self.timer.stop();self.capture_timer.stop();self.hotkeys.close()
  if self.listening:backend.U.RemoveClipboardFormatListener(int(self.window.winId()))
  self.app.removeNativeEventFilter(self.native_filter);self.executor.shutdown(wait=False,cancel_futures=True)
  self.store.items.clear();self.tray.hide();self.window.hide();self.app.exit(0)

def main():
 mutex=backend.K.CreateMutexW(None,False,backend.MUTEX)
 if backend.C.get_last_error()==183:
  event=backend.K.CreateEventW(None,False,False,backend.EVENT);backend.K.SetEvent(event);return
 app=QApplication(sys.argv);app.setQuitOnLastWindowClosed(False);app.setApplicationName('Clipboard Float');app.setWindowIcon(QIcon(str(Path(__file__).parent/'assets/clipboard-float.ico')));controller=Controller(app,start_hidden='--background' in sys.argv);app._controller=controller;app.exec()
if __name__=='__main__':main()
