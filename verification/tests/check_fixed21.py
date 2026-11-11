import ast, json, textwrap
from pathlib import Path
from io import StringIO
from contextlib import redirect_stdout
p=Path(__file__).resolve().parents[2]
source=(p/'firmware'/'main.py').read_text(encoding='utf-8')
tree=ast.parse(source)
env={'DRIFT_LIMIT_PH':.4,'ADC_MIN':500,'ADC_MAX':45000,'STUCK_LIMIT_PH':.1,'STUCK_DURATION_MS':15000}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('decide','drift_summary','signal_out_of_range','stuck_summary')],type_ignores=[]),'helpers','exec'),env)
block=source[source.index('        ready = sample_elapsed'):source.index('        if calibration_valid and sample_id is None:')]
code=compile(textwrap.dedent(block),'decision','exec')
def run(first=4,last=4,stable=True,age=21000,missing=False,late=False,valid=True):
    capture={s:dict(ph=first if s<=3 else last,filtered_ph=first if s<=3 else last,raw=34000,actual_ms=s*1000,on_time=True) for s in range(1,21)}
    if missing: del capture[18]
    if late: capture[3]['on_time']=False
    ns=dict(env,capture=capture,sample_elapsed=age,SETTLING_DEADLINE_MS=21000,
        ph=last,filtered_ph=last,raw=34000,settled=stable,calibration_valid=valid,fault=False,
        stuck_baseline=None,known_buffer_changed=False,
        evaluating=age>=21000,deadline_checked=False,sample_stopped=False,
        drift_info=None,elapsed=age,sample_id='x',spread=.1,json=json)
    with redirect_stdout(StringIO()):exec(code,ns)
    return ns
assert run(age=20000)['verdict'] is None
assert run()['verdict']=='GASTRIC_RANGE'
assert run(first=7,last=7)['verdict']=='DO_NOT_FEED'
assert run(last=4.401)['reason']=='DRIFT_FAILURE'
assert run(first=7,last=6.599)['reason']=='DRIFT_FAILURE'
assert run(last=4.4)['reason']=='VALID'
assert run(stable=False)['reason']=='UNABLE_TO_SETTLE'
assert run(missing=True)['reason']=='MISSING_TIMED_READINGS'
assert run(late=True)['reason']=='MISSING_TIMED_READINGS'
assert run(valid=False)['reason']=='CALIBRATION_INVALID'
result=run()['drift_info']
assert result['actual_first_ms']==[1000,2000,3000]
assert result['actual_last_ms']==[18000,19000,20000]
for filename in ('main.py','laptop_monitor_stop.py'):
    compile((p/('firmware' if filename == 'main.py' else 'software')/filename).read_text(encoding='utf-8'),filename,'exec')
print('PASS: 21-second decision, correct six readings, threshold equality/directions, missing/late readings, settling, calibration, syntax.')
