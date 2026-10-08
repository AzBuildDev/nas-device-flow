import socket,struct,unittest
from device_names import read_name,encode_name,parse_names
class NameTests(unittest.TestCase):
 def packet(self, owner, kind, payload, ttl=120):
  return struct.pack('!6H',0,0x8400,0,1,0,0)+encode_name(owner)+struct.pack('!HHIH',kind,1,ttl,len(payload))+payload
 def test_reverse_name(self):
  p=self.packet('175.50.168.192.in-addr.arpa',12,encode_name('Alice-MacBook.local'))
  self.assertEqual(parse_names(p,{'192.168.50.175'}),{'192.168.50.175':'Alice-MacBook'})
 def test_address_record(self):
  p=self.packet('Living-Room-TV.local',1,socket.inet_aton('192.168.50.180'))
  self.assertEqual(parse_names(p,{'192.168.50.180'}),{'192.168.50.180':'Living-Room-TV'})
 def test_other_device_and_goodbye_ignored(self):
  p=self.packet('Other.local',1,socket.inet_aton('192.168.50.180'));self.assertEqual(parse_names(p,{'192.168.50.175'}),{})
  p=self.packet('TV.local',1,socket.inet_aton('192.168.50.180'),ttl=0);self.assertEqual(parse_names(p,{'192.168.50.180'}),{})
 def test_compression(self):
  data=encode_name('MacBook.local')+b'\xc0\x00';self.assertEqual(read_name(data,len(data)-2)[0],'MacBook.local')
 def test_malformed_packet_and_loop(self):
  self.assertEqual(parse_names(b'garbage',{'192.168.50.175'}),{})
  with self.assertRaises(ValueError):read_name(b'\xc0\x00',0)
 def test_generic_localhost_is_not_a_device_name(self):
  p=self.packet('localhost.local',1,socket.inet_aton('192.168.50.180'));self.assertEqual(parse_names(p,{'192.168.50.180'}),{})
 def test_nonlocal_name_not_used(self):
  p=self.packet('TV.example.com',1,socket.inet_aton('192.168.50.180'));self.assertEqual(parse_names(p,{'192.168.50.180'}),{})
if __name__=='__main__':unittest.main()
