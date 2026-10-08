"""Bounded Mihomo telemetry cache; never exposes connection destinations or API credentials."""
import copy, threading, time
from collections import deque

class TrafficStats:
    def __init__(self):
        self.lock=threading.Lock();self.history=deque(maxlen=180)
        self.state={'ok':False,'updated':0,'up':0,'down':0,'upload_total':0,'download_total':0,'connections':0,'memory':0}
    def update(self, traffic, connections=None, now=None):
        def number(value):
            return max(0,int(value)) if isinstance(value,(int,float)) else 0
        now=time.time() if now is None else now
        with self.lock:
            self.state.update(ok=True,updated=now,up=number(traffic.get('up')),down=number(traffic.get('down')))
            if connections is not None:
                self.state.update(upload_total=number(connections.get('uploadTotal')),download_total=number(connections.get('downloadTotal')),connections=len(connections.get('connections') or []),memory=number(connections.get('memory')))
            self.history.append({'time':now,'up':self.state['up'],'down':self.state['down']})
    def failed(self):
        with self.lock:self.state['ok']=False
    def snapshot(self):
        with self.lock:
            result=copy.deepcopy(self.state);result['history']=list(self.history)
        result['ok']=result['ok'] and time.time()-result['updated']<8
        return result
