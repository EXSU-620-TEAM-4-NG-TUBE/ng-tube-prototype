"""Run the actual firmware loop with a virtual ADC, button, clock and USB."""
import ast,json,io
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
src=(Path(__file__).resolve().parents[2]/'firmware'/'main.py').read_text(encoding='utf-8')
tree=ast.parse(src)
tree.body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
code=compile(tree,'main.py','exec')
def run(values,baseline,known_change=False, duration=22500, details=False, restart_at=None, press_at=None, ring_details=False):
    clock=[0];queue=[];env={};history=[];adc_calls=[];restarted=[False]
    commands=[{'command':'TIME_SYNC','unix_time':1800000000},
              {'command':'NEW_SAMPLE','sample_id':'test','baseline_ph':baseline,'known_buffer_changed':known_change}]
    queue.extend(''.join(json.dumps(c)+'\n' for c in commands))
    class Pin:
        IN=0;PULL_UP=1
        def __init__(self,*a):pass
        def value(self):return 0 if press_at is not None and press_at<=clock[0]<press_at+200 else 1
    class ADC:
        def __init__(self,*a):pass
        def read_u16(self):
            adc_calls.append(clock[0])
            second=max(1,(clock[0]-(env.get('sample_started_ms') or 0))//1000)
            value=values(second)
            return value if type(value) is int else round(34000+(value-4)*5000/3)
    class Ring:
        def __init__(self,*a):pass
        def fill(self,c):history.append((clock[0],c))
        def write(self):pass
    class Poll:
        def register(self,*a):pass
        def poll(self,*a):return bool(queue)
    def sleep(ms):
        clock[0]+=ms
        if restart_at is not None and clock[0]>=restart_at and not restarted[0]:
            restarted[0]=True
            queue.extend(json.dumps({'command':'NEW_SAMPLE','sample_id':'second'})+'\n')
        if clock[0]>duration:raise KeyboardInterrupt()
    def fopen(path,*a):
        assert path=='calibration_record.json',path
        return io.StringIO(json.dumps(dict(raw_ph4=34000,raw_ph7=39000,calibration_id='cal',operator='test',calibrated_at_unix=1800000000)))
    env.update(ADC=ADC,Pin=Pin,ticks_ms=lambda:clock[0],ticks_diff=lambda a,b:a-b,sleep_ms=sleep,
        neopixel=SimpleNamespace(NeoPixel=Ring),json=json,os=SimpleNamespace(),
        sys=SimpleNamespace(stdin=SimpleNamespace(read=lambda n:queue.pop(0) if queue else '')),
        select=SimpleNamespace(poll=Poll,POLLIN=1),open=fopen)
    with redirect_stdout(io.StringIO()) as out:
        try:exec(code,env)
        except KeyboardInterrupt:pass
    rows=[json.loads(s) for s in out.getvalue().splitlines()]
    result=next(r for r in rows if r.get('event_type')=='FIXED_WINDOW_RESULT')
    assert result['sample_elapsed_ms']>=21000
    assert result['sample_elapsed_ms']<21250
    assert all(r.get('verdict') is None for r in rows if r.get('sample_elapsed_ms') is not None and r['sample_elapsed_ms']<21000)
    if ring_details:return rows,adc_calls,history
    return (rows,adc_calls) if details else result
assert run(lambda s:4.0,7.0)['reason']=='VALID'
assert run(lambda s:7.0,7.0,True)['reason']=='STUCK_FAILURE'
assert run(lambda s:7.0,7.0)['reason']=='VALID' # Similar routine samples are not stuck.
assert run(lambda s:4.0 if s<2 else 7.0,4.0,True)['verdict']=='PROBE_RESPONSE_DETECTED'
assert run(lambda s:4.0 if s<5 else 7.0,4.0,True)['reason']=='UNABLE_TO_SETTLE'
assert run(lambda s:4.0,None)['reason']=='VALID'
assert run(lambda s:65535 if s==5 else 4.0,7.0)['reason']=='SIGNAL_OUT_OF_RANGE'
assert run(lambda s:4.0 if s<5 else 4.6,7.0)['reason']=='DRIFT_FAILURE'
assert run(lambda s:4.0+(.22 if s%2 else -.22),7.0)['reason']=='UNABLE_TO_SETTLE'
print('PASS: actual firmware loop, 21-second publication, stable/stuck/no-baseline/signal/drift/unsettled scenarios.')
rows,calls=run(lambda s:7.0 if s<=20 else 65535,None,duration=60000,details=True)
held=[r for r in rows if r.get('result_held') and not r.get('event_type')]
assert len(held)>30
assert all(r['state']=='CRITICAL' and r['reason']=='VALID' for r in held)
assert len({r['pH_estimate'] for r in held})==1
assert len({r['sample_elapsed_ms'] for r in held})==1
assert max(calls)<21000, calls
rows,calls=run(lambda s:4.0,None,duration=55000,details=True,restart_at=30000)
assert len([r for r in rows if r.get('event_type')=='FIXED_WINDOW_RESULT'])==2
assert any(t>30000 for t in calls)
assert any(r.get('sample_id')=='second' and r.get('result_held') for r in rows)
print('PASS: result and pH held for 60 seconds; no ADC sampling after completion; NEW SAMPLE resumes acquisition.')
rows,calls,history=run(lambda s:7.0,None,duration=40000,press_at=30000,ring_details=True)
stops=[r for r in rows if r.get('reason')=='SAMPLE_STOPPED']
assert stops and all(r.get('ring_command')=='OFF' for r in stops)
after=[colour for ms,colour in history if ms>=31000]
assert len(after)>=5 and all(c==(0,0,0) for c in after)
assert max(calls)<21000
print('PASS: physical stop after critical result repeatedly commands ring OFF; no measurement restarts.')
