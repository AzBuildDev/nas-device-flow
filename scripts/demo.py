#!/usr/bin/env python3
"""Fictional local demo. Does not read runtime, reach routers or save changes."""
import argparse,json,math,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
DEVICES=[{'mac':'02:00:00:00:00:'+str(i).zfill(2),'ip':'192.168.50.'+str(100+i),'label':name,'name':name,'online':True,'enabled':i<3,'proxy_traffic':{'upload':i*1200000,'download':i*32000000,'total':i*33200000},'proxy_traffic_ok':True,'proxy_traffic_since':time.time()-3600} for i,name in enumerate(['iPhone 示例','电脑 示例','电视 示例','新设备 示例'],1)]
class Demo(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,obj,status=200):
  raw=json.dumps(obj,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  now=time.time()
  if self.path=='/':
   html=(Path(__file__).resolve().parents[1]/'app/index.html').read_text().replace('{{GATEWAY}}','192.168.50.250').replace('<main>','<main><p style="text-align:center;color:#946000">演示数据 · 未连接真实网络 · 开关仅修改本地示例</p>')
   self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(html.encode());return
  if self.path=='/api/devices':return self.send({'devices':DEVICES,'router_sync':{'ok':False},'csrf':'demo','core_ok':True,'version':'demo','dhcp':True,'error':'演示模式：所有设备和流量均为虚构。','gateway':'192.168.50.250'})
  if self.path=='/api/stats':return self.send({'ok':True,'updated':now,'up':210000,'down':2800000,'upload_total':120000000,'download_total':920000000,'connections':28,'memory':64000000,'history':[{'time':now-179+i,'up':180000+100000*math.sin(i/11)**2,'down':1600000+1500000*math.sin(i/19)**2} for i in range(180)],'device_traffic':{'ok':True,'since':now-3600,'devices':{d['mac']:d['proxy_traffic'] for d in DEVICES}}})
  if self.path=='/api/subscriptions':return self.send({'subscriptions':[],'current':'演示模式','nodes':0})
  self.send({'error':'演示接口不存在'},404)
 def do_POST(self):
  if self.path!='/api/device':return self.send({'error':'演示模式不保存订阅或认证配置'},400)
  n=int(self.headers.get('Content-Length','0'))
  if not 0<n<=4096:return self.send({'error':'请求无效'},400)
  try:body=json.loads(self.rfile.read(n))
  except ValueError:return self.send({'error':'请求无效'},400)
  for d in DEVICES:
   if d['mac']==body.get('mac'):
    if type(body.get('enabled')) is bool:d['enabled']=body['enabled']
    if isinstance(body.get('name'),str):d['label']=d['name']=body['name'][:60]
    return self.send({'ok':True,'warning':'仅更改虚构示例，未修改任何网络配置'})
  self.send({'error':'示例设备不存在'},404)
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=9088);a=parser.parse_args()
 print(f'Fictional demo: http://127.0.0.1:{a.port}',flush=True)
 ThreadingHTTPServer(('127.0.0.1',a.port),Demo).serve_forever()
