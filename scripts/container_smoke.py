"""Offline smoke check; run in the built container with --network none."""
import importlib.util,json,os,subprocess,tempfile,time
from pathlib import Path
from urllib.request import Request,urlopen
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bootstrap',root/'scripts/initialize.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
with tempfile.TemporaryDirectory() as tmp:
 b.initialize(tmp,{},'fictional-smoke-password','https://example.invalid/fixture.yaml')
 runtime=Path(tmp)/'runtime';data=runtime/'control-center'
 # dnsmasq --test parses configuration without listening or starting DHCP.
 (data/'dnsmasq.conf').write_text(b.Settings().dnsmasq(data))
 subprocess.run(['dnsmasq','--test','--conf-file='+str(data/'dnsmasq.conf')],check=True)
 env=dict(os.environ,NDF_DATA_ROOT=str(runtime))
 process=subprocess.Popen(['python3','/app/server.py'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(30):
   try:
    with urlopen('http://127.0.0.1:9080/health',timeout=1) as r:assert json.load(r)=={'ok':True}
    break
   except OSError:time.sleep(.1)
  else:raise RuntimeError('controller did not become healthy')
  req=Request('http://127.0.0.1:9080/api/login',data=json.dumps({'password':'fictional-smoke-password'}).encode(),headers={'Content-Type':'application/json'})
  with urlopen(req,timeout=2) as r:assert r.status==200 and 'csrf' in json.load(r)
  assert not (data/'dhcp.enabled').exists()
  print('PASS: dnsmasq syntax, controller startup, health, login, DHCP remains OFF')
 finally:
  process.terminate();process.wait(timeout=10)
