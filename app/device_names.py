"""Bounded mDNS reverse lookup. Names are hints, never device identity or policy keys."""
import ipaddress, socket, struct, time

def read_name(data, offset):
    labels=[]; visited=set(); end=None
    while True:
        if offset>=len(data) or offset in visited or len(visited)>128: raise ValueError('invalid DNS name')
        visited.add(offset); length=data[offset]
        if length & 0xc0 == 0xc0:
            if offset+1>=len(data): raise ValueError('truncated pointer')
            if end is None: end=offset+2
            offset=((length&0x3f)<<8)|data[offset+1]; continue
        if length & 0xc0: raise ValueError('invalid label')
        offset+=1
        if not length: return '.'.join(labels), end if end is not None else offset
        if offset+length>len(data): raise ValueError('truncated label')
        labels.append(data[offset:offset+length].decode('utf-8',errors='replace')); offset+=length
        if sum(len(x)+1 for x in labels)>255: raise ValueError('name too long')

def encode_name(name):
    return b''.join(bytes([len(x)])+x.encode('ascii') for x in name.split('.'))+b'\0'

def parse_names(data, expected):
    result={}
    if len(data)<12: return result
    _,flags,questions,answers,authority,additional=struct.unpack('!6H',data[:12])
    if not flags&0x8000 or questions>128 or answers+authority+additional>256: return result
    offset=12
    try:
        for _ in range(questions):
            _,offset=read_name(data,offset);offset+=4
            if offset>len(data): raise ValueError()
        for _ in range(answers+authority+additional):
            owner,offset=read_name(data,offset)
            if offset+10>len(data): raise ValueError()
            kind,cls,ttl,length=struct.unpack('!HHIH',data[offset:offset+10]);offset+=10
            end=offset+length
            if end>len(data): raise ValueError()
            ip=None; hostname=None
            if cls&0x7fff==1 and ttl>0:
                if kind==12 and owner.lower().endswith('.in-addr.arpa'):
                    part=owner.lower()[:-13].split('.')
                    if len(part)==4:
                        ip=str(ipaddress.IPv4Address('.'.join(reversed(part))));hostname,_=read_name(data,offset)
                elif kind==1 and length==4:
                    ip=socket.inet_ntoa(data[offset:end]);hostname=owner
            if ip in expected and hostname and hostname.lower().endswith('.local'):
                label=hostname[:-6].strip()
                if label and label.casefold()!='localhost' and not label.startswith('_') and not any(ord(x)<32 for x in label): result[ip]=label[:80]
            offset=end
    except (ValueError,struct.error): return {}
    return result

def discover_names(ips, timeout=2):
    ips={str(ipaddress.IPv4Address(ip)) for ip in ips if ip}
    if not ips:return {}
    result={}; sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try:
        sock.bind(('0.0.0.0',0));sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,255);sock.settimeout(.2)
        # Ephemeral source port requests legacy unicast replies; no daemon or UDP 5353 listener needed.
        for ip in sorted(ips):
            question=encode_name('.'.join(reversed(ip.split('.')))+'.in-addr.arpa')+struct.pack('!HH',12,1)
            packet=struct.pack('!6H',0,0,1,0,0,0)+question
            sock.sendto(packet,('224.0.0.251',5353))
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:data,source=sock.recvfrom(9000)
            except socket.timeout:continue
            if source[1]!=5353:continue
            result.update(parse_names(data,ips))
    finally:sock.close()
    return result
