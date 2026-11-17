import unittest,math,struct,time
from types import SimpleNamespace
from filee_motion import Spring,point_at,angle_of,index_at
from floating_clipboard import wedge,image_of,FloatMenu,backend
from PySide6.QtWidgets import QApplication,QMenu
from PySide6.QtCore import QPointF,Qt,QEvent
from PySide6.QtGui import QKeyEvent
class MotionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_slice_centers_and_wrap(self):
  for i in range(6):
   x,y=point_at(290,290,167,i*math.tau/6)
   self.assertEqual(index_at(angle_of(290,290,x,y),6),i)
   self.assertTrue(wedge(290,290,104,230,i*math.tau/6).contains(QPointF(x,y)))
  self.assertEqual(index_at(math.tau-.01,6),0)
 def test_spring_handles_late_frame_and_settles(self):
  spring=Spring()
  for _ in range(120):spring.step(1,.05)
  self.assertEqual(spring.value,1);self.assertEqual(spring.velocity,0)
  for _ in range(100):spring.step(0,.016)
  self.assertLess(abs(spring.value),.001)
 def test_dib_thumbnail_decoding(self):
  header=struct.pack('<IiiHHIIiiII',40,2,2,1,32,0,16,0,0,0,0)
  image=image_of({'formats':{8:header+bytes([0,0,255,255])*4}})
  self.assertFalse(image.isNull());self.assertEqual(image.width(),2)
 def test_close_deactivation_keeps_pending_action(self):
  controller=SimpleNamespace(store=backend.Store(),context=QMenu())
  window=FloatMenu(controller);calls=[]
  window.closing=True;window.closing_at=time.perf_counter()-.2;window.after_close=lambda:calls.append('paste')
  window.dismiss() # Native deactivation must not erase the pending paste.
  self.assertIsNotNone(window.after_close)
  window.frame();self.assertEqual(calls,['paste']);self.assertFalse(window.timer.isActive());window.deleteLater()
 def test_tab_pages_from_search_and_menu_and_wraps(self):
  store=backend.Store()
  for n in range(13):store.add({13:str(n).encode()},f'Clip {n}','Text')
  window=FloatMenu(SimpleNamespace(store=store,context=QMenu()))
  def tab(target,repeat=False,key=Qt.Key.Key_Tab,mods=Qt.KeyboardModifier.NoModifier):
   QApplication.sendEvent(target,QKeyEvent(QEvent.Type.KeyPress,key,mods,'',repeat))
  tab(window.search);self.assertEqual(window.page,1)
  tab(window);self.assertEqual(window.page,2)
  tab(window.search);self.assertEqual(window.page,0)
  tab(window.search,repeat=True);self.assertEqual(window.page,0)
  tab(window.search,key=Qt.Key.Key_Backtab,mods=Qt.KeyboardModifier.ShiftModifier);self.assertEqual(window.page,2)
  window.deleteLater()
if __name__=='__main__':unittest.main()
