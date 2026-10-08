#!/usr/bin/env python3
"""Run inside a isolated veth network namespace; verify DHCP broadcasts without touching host DHCP."""
import argparse,json,os,socket,struct,subprocess,time
p=argparse.ArgumentParser();p.add_argument('--interface',default='eth0');p.add_argument('--exchange',action='store_true');p.add_argument('--release',action='store_true');p.add_argument('--release-only');p.add_argument('--old-ip');p.add_argument('--request-ip');p.add_argument('--expected-server',required=True);p.add_argument('--expected-gateway',required=True);p.add_argument('--expected-dns',required=True);p.add_argument('--prefix',type=int,default=24);args=p.parse_args()
iface=args.interface
if os.environ.get('NDF_ISOLATED_DHCP_TEST') != '1':raise SystemExit('Use isolated-dhcp-test.sh; never probe a production LAN')
link=json.loads(subprocess.check_output(['ip','-d','-j','link','show',iface]))[0]
if link.get('linkinfo',{}).get('info_kind')!='veth':raise SystemExit('Protocol test requires an isolated veth interface')
# Namespace /sys still sees host, so obtain namespace interface MAC via ip.
mac=bytes.fromhex(json.loads(subprocess.check_output(['ip','-j','link','show',iface]))[0]['address'].replace(':',''))
xid=os.urandom(4);raw=socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(0x0800));raw.bind((iface,0));raw.settimeout(.5)
def checksum(data):
 if len(data)%2:data+=b'\x00'
 s=sum(struct.unpack('!%dH'%(len(data)//2),data));s=(s>>16)+(s&65535);s+=(s>>16);return (~s)&65535

def send(kind,requested=None,server=None,client='0.0.0.0'):
 boot=b'\x01\x01\x06\x00'+xid+struct.pack('!HH',0,0x8000)+socket.inet_aton(client)+b'\x00'*12+mac+b'\x00'*10+b'\x00'*192+b'\x63\x82\x53\x63'
 hostname=b'NAS-route-test'
 opts=b'\x35\x01'+bytes([kind])+b'\x3d\x07\x01'+mac+bytes([12,len(hostname)])+hostname+b'\x37\x04\x01\x03\x06\x33'
 if requested:opts+=b'\x32\x04'+socket.inet_aton(requested)
 if server:opts+=b'\x36\x04'+socket.inet_aton(server)
 payload=boot+opts+b'\xff';udp=struct.pack('!HHHH',68,67,8+len(payload),0)+payload
 iph=struct.pack('!BBHHHBBH4s4s',0x45,0,20+len(udp),0,0,64,17,0,socket.inet_aton(client),b'\xff'*4);iph=iph[:10]+struct.pack('!H',checksum(iph))+iph[12:]
 raw.send(b'\xff'*6+mac+b'\x08\x00'+iph+udp)

def receive(seconds):
 results=[];end=time.time()+seconds
 while time.time()<end:
  try:frame=raw.recv(65535)
  except socket.timeout:continue
  if len(frame)<300 or frame[23]!=17:continue
  ihl=(frame[14]&15)*4;udpstart=14+ihl
  if struct.unpack('!HH',frame[udpstart:udpstart+4])!=(67,68):continue
  b=frame[udpstart+8:]
  if b[4:8]!=xid or b[28:34]!=mac:continue
  opts={};i=240
  while i<len(b):
   code=b[i];i+=1
   if code==255:break
   if code==0:continue
   if i>=len(b):break
   n=b[i];i+=1
   if i+n>len(b):break
   opts[code]=b[i:i+n];i+=n
  result={'type':opts.get(53,b'\x00')[0],'ip':socket.inet_ntoa(b[16:20]),'server':socket.inet_ntoa(opts[54]) if 54 in opts else socket.inet_ntoa(frame[26:30]),'router':[socket.inet_ntoa(opts[3][i:i+4]) for i in range(0,len(opts.get(3,b'')),4)],'dns':[socket.inet_ntoa(opts[6][i:i+4]) for i in range(0,len(opts.get(6,b'')),4)]}
  results.append(result)
 return results
if args.release_only:
 send(7,server=args.expected_server,client=args.release_only);raise SystemExit(0)
if args.request_ip:
 send(3,args.request_ip);replies=receive(5)
 ack=next(r for r in replies if r['type']==5 and r['server']==args.expected_server)
 assert ack['ip']==args.request_ip and ack['router']==[args.expected_gateway] and ack['dns']==[args.expected_dns],ack
 print(json.dumps({'retained_address_ack':ack}),flush=True)
 if args.release:send(7,server=ack['server'],client=ack['ip'])
 raise SystemExit(0)
if args.old_ip:
 # INIT-REBOOT for an unknown address outside the new pool must be rejected,
 # allowing the client to immediately discover its new automatic configuration.
 send(3,args.old_ip);replies=receive(5)
 assert any(r['type']==6 and r['server']==args.expected_server for r in replies),replies
 print(json.dumps({'old_lease_nak':replies}),flush=True)
send(1);offers=receive(5);report={'offers':offers,'mac':mac.hex(':')};print(json.dumps(report),flush=True)
if args.exchange:
 offer=next(o for o in offers if o['type']==2 and o['server']==args.expected_server);send(3,offer['ip'],offer['server']);acks=receive(5);ack=next(a for a in acks if a['type']==5)
 assert ack['router']==[args.expected_gateway] and ack['dns']==[args.expected_dns],ack
 print(json.dumps({'ack':ack}),flush=True)
 subprocess.run(['ip','addr','add',ack['ip']+'/'+str(args.prefix),'dev',iface],check=True);subprocess.run(['ip','route','add','default','via',args.expected_gateway],check=True)
 if args.release:send(7,server=offer['server'],client=ack['ip'])
