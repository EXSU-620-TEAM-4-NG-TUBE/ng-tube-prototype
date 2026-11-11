"""Desktop checks only; no hardware or serial access."""
import ast
import json
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO

folder = Path(__file__).resolve().parents[2]
def definitions(file, names):
    tree = ast.parse((folder/('firmware' if file == 'main.py' else 'software')/file).read_text(encoding='utf-8'))
    return compile(ast.Module(body=[n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names], type_ignores=[]), file, 'exec')

class Ring:
    color = None
    def fill(self, color): self.color = color
    def write(self): pass

clock = [50000]
ns = dict(json=json, ticks_ms=lambda: clock[0], ticks_diff=lambda a,b:a-b,
          sample_id='sample_a', sample_started_ms=1000, start=0,
          sample_stopped=False, stopped_elapsed=None, window=[7]*10,
          stable_since=30000, OFF=(0,0,0), CYAN=(0,8,8), ring=Ring(),
          last_measurement={'pH_estimate':7, 'state':'CRITICAL','verdict':'DO_NOT_FEED'})
exec(definitions('main.py', ['stop_sample','start_sample','decide']), ns)
with redirect_stdout(StringIO()) as output:
    ns['stop_sample']()
    frozen = ns['stopped_elapsed']
    clock[0] += 130000
    ns['stop_sample']()
    assert ns['stopped_elapsed'] == frozen
    assert ns['ring'].color == (0,0,0)
    assert ns['last_measurement']['state'] == 'CRITICAL'
    ns['start_sample']('sample_a')
    assert ns['sample_stopped']  # Duplicate request cannot resume old sample.
    ns['start_sample']('sample_b')
    assert not ns['sample_stopped'] and ns['window'] == []
    assert ns['sample_started_ms'] == clock[0] and ns['start'] == 0
    assert ns['last_measurement'] is None
events = [json.loads(s) for s in output.getvalue().splitlines()]
assert sum(e['event_type']=='SAMPLE_STOPPED' for e in events) == 1
assert ns['decide'](4, True, False, False)[2] == 'CALIBRATION_INVALID'

env = {'MUTE_SECONDS':120}
exec(definitions('laptop_monitor_stop.py', ['Alarm','SampleGate']), env)
a = env['Alarm']()
def reading(state):
    return dict(state=state, settled=True, calibration_valid=True, reason='VALID')
assert a.update(reading('CRITICAL')) == 'CRITICAL'
a.acknowledge(1)
assert a.latched and a.acknowledged
assert a.update(dict(state='TECHNICAL', settled=False, calibration_valid=True, reason='SAMPLE_STOPPED')) == 'TECHNICAL'
assert a.latched  # Stopping cannot erase critical history.
a.muted_until = 0
assert a.update(reading('CRITICAL')) == 'CRITICAL'
assert a.update(reading('NORMAL')) == 'NORMAL' and not a.latched
for file in ('main.py','laptop_monitor_stop.py'):
    compile((folder/('firmware' if file == 'main.py' else 'software')/file).read_text(encoding='utf-8'), file, 'exec')
print('PASS: stop idempotence, history, LED off, duplicate prevention, restart, calibration gating, latch/ACK and syntax.')
