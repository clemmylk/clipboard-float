"""Filee-derived polar geometry and spring stepping, ported to Python.
Copyright (c) 2026 Myeonggu Kim (KnifeLemon) and Filee contributors.
MIT license: third_party/Filee/LICENSE. Adaptation: clipboard history UI.
"""
import math
ACCENT='#7F77DD';PAGE='#F6F5F1';SURFACE='#FFFFFF';ALT='#EFEDE6';TEXT='#1F1E1D';MUTED='#6B6A66'

def point_at(cx,cy,radius,angle):return cx+radius*math.sin(angle),cy-radius*math.cos(angle)
def angle_of(cx,cy,x,y):return math.atan2(x-cx,cy-y)%(2*math.pi)
def index_at(angle,count):return math.floor((angle+math.pi/count)/(2*math.pi/count))%count if count else -1
class Spring:
 def __init__(self,value=0):self.value=value;self.velocity=0
 def step(self,target,dt,stiffness=320,damping=20):
  steps=max(1,math.ceil(dt/(1/120)));h=dt/steps
  for _ in range(steps):
   force=stiffness*(target-self.value)-damping*self.velocity
   self.velocity+=force*h;self.value+=self.velocity*h
  settled=abs(target-self.value)<.001 and abs(self.velocity)<.01
  if settled:self.value=target;self.velocity=0
  return not settled
