"""Exercise the real monitor loop with fake UI/USB. No physical port opens."""
import ast, json, sqlite3, tempfile, uuid
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
source=(Path(__file__).parent/'laptop_monitor_stop.py').read_text(encoding='utf-8')
tree=ast.parse(source)
tree.body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom)) and not (isinstance(n,ast.If))]
clock=[0.0]; step=[0]; widgets=[]; displays=[]; connected=[]; played=[]
class Widget:
    def __init__(self,*a,**kw): self.kw=kw; self.hidden=False; widgets.append(self)
    def pack(self,*a,**kw): pass
    def config(self,**kw):
        self.kw.update(kw)
        if 'text' in kw: displays.append((step[0],kw['text']))
    def cget(self,key): return self.kw.get(key,'')
    def title(self,*a): pass
    def geometry(self,*a): pass
    def minsize(self,*a): pass
    configure=config
    def withdraw(self): self.hidden=True
    def deiconify(self): self.hidden=False
    def lift(self): pass
    def state(self): return 'withdrawn' if self.hidden else 'normal'
    def protocol(self,name,fn): self.close=fn
    def destroy(self): pass
    def update(self):
        step[0]+=1;clock[0]+=1
        if step[0] in (4,50):
            next(w for w in widgets if w.kw.get('text')=='NEW SAMPLE').kw['command']()
        if step[0]==85:self.close()
class Var:
    def __init__(self,value=''): self.value=value
    def get(self): return self.value
    def set(self,value): self.value=value
class SerialError(Exception):pass
class Port:
    def __init__(self,*a,**kw):
        if 40 <= step[0] < 45:raise SerialError('Disconnected')
        connected.append(step[0]);self.sample=None;self.start=step[0];self.sample_start=0
    def write(self,data):
        cmd=json.loads(data)
        if cmd['command']=='NEW_SAMPLE':self.sample=cmd['sample_id'];self.sample_start=step[0]
        return len(data)
    @property
    def in_waiting(self):return 4096
    def read(self,*a):
        if 40<=step[0]<45:raise SerialError('Disconnected')
        age=(step[0]-self.sample_start)*1000 if self.sample else None
        valid=age is not None and age>=21000
        stopped=self.sample is not None and 30<=step[0]<40
        msg=dict(state='TECHNICAL' if stopped or not valid else 'NORMAL',reason='SAMPLE_STOPPED' if stopped else 'VALID' if valid else 'MEASURING',
            elapsed_ms=(step[0]-self.start)*1000,pH_estimate=None if stopped else 4.0,
            settled=valid and not stopped,calibration_valid=True,verdict='GASTRIC_RANGE' if valid and not stopped else None,
            sample_id=self.sample,sample_elapsed_ms=age,calibrated_at_unix=1800000000,
            calibration_remaining_ms=500000,firmware_version='sample_simple_v7',input_source='SENSOR')
        return (json.dumps(msg)+'\n').encode()
    def close(self):pass
class Audio:
    def stop(self):pass
    def play(self,state):played.append((step[0],state))
class Phone:
    def __init__(self):self.pending=set();self.sent=set()
    def drain(self):return []
    def submit(self,sample_id,*args,**kw):
        if sample_id in self.sent:return None
        self.sent.add(sample_id)
        return {'sample_id':sample_id,'topic':'MOCK_NO_NETWORK'}
tk=SimpleNamespace(Tk=Widget,Toplevel=Widget,Frame=Widget,Label=Widget,Entry=Widget,Button=Widget,StringVar=Var)
with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
    env=dict(json=json,sqlite3=sqlite3,uuid=uuid,Path=Path,datetime=datetime,timezone=timezone,
        tk=tk,serial=SimpleNamespace(Serial=Port,SerialException=SerialError),
        list_ports=SimpleNamespace(comports=lambda:[SimpleNamespace(device='COM8',serial_number='test-device')]),
        time=SimpleNamespace(monotonic=lambda:clock[0],time=lambda:1800000000+clock[0],sleep=lambda x:None),
        __file__=str(Path(d)/'monitor.py'),input=lambda prompt:'TEST',__name__='test',PhoneNotifications=Phone)
    exec(compile(tree,'monitor','exec'),env)
    env['Audio']=Audio
    env['main']()
    events=[json.loads(line) for path in (Path(d)/'bench_logs').glob('*.jsonl') for line in path.read_text().splitlines()]
    assert len(connected)>=2,connected
    pushes=[e for e in events if e['kind']=='PHONE_NOTIFICATION_QUEUED']
    assert len(pushes)==2,pushes
    requests=[e['payload'] for e in events if e['kind']=='NEW_SAMPLE_REQUEST']
    assert requests and all(r['known_buffer_changed'] is False and r['baseline_ph'] is None for r in requests)
    assert any(e['kind']=='SAMPLE_INTERRUPTED' for e in events)
    assert any('Test stopped' in str(text) for _,text in displays)
    assert any('Ready — start' in str(text) for at,text in displays if at>=45)
    assert any('Normal/ Gastric' in str(text) for at,text in displays if at>=71)
    assert not any(at<25 for at,state in played),played
    result=env['visible_result']
    assert result(dict(state='NORMAL',reason='VALID',sample_elapsed_ms=21000,settled=True,
        calibration_valid=True,pH_estimate=7.0,verdict='PROBE_RESPONSE_DETECTED'),'test',True)[1]=='Probe response detected — check complete'
    assert result(None,None,True)[0]=='READY'
    for reason,label in [('STUCK_FAILURE','Technical/Stuck; REPEAT'),('DRIFT_FAILURE','Technical/Drifting; REPEAT')]:
        r=dict(state='TECHNICAL',reason=reason,sample_elapsed_ms=21000,pH_estimate=None)
        assert result(r,'sample',True)[1]==label
print('PASS: full monitor loop, neutral startup, no early audio, stopped null pH, USB reconnect, fresh sample, verdict labels.')
