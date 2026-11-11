import ast
from pathlib import Path
source=(Path(__file__).parent/'main.py').read_text(encoding='utf-8')
tree=ast.parse(source)
names=('update_clock','calibration_remaining')
clock=[100]
env=dict(ticks_ms=lambda:clock[0],ticks_diff=lambda a,b:a-b,
         clock_tick=100,clock_unix_ms=None,calibration_load_error=None,
         calibrated_at=1800000000,CAL_LIFETIME_SECONDS=604800)
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'weekly','exec'),env)
remaining=env['calibration_remaining']
assert remaining()==0 # Reboot requires laptop time.
env['clock_unix_ms']=1800000000*1000
assert remaining()==604800000
env['clock_unix_ms']+=(604800-1)*1000
assert remaining()==1000
clock[0]+=1000
env['update_clock']()
assert remaining()==0 # Seven-day boundary.
env['clock_unix_ms']=(1800000000+3*86400)*1000
assert remaining()==4*86400*1000 # Restart on day three does not grant seven days.
env['clock_unix_ms']=(1800000000-1)*1000
assert remaining()==0
env['clock_unix_ms']=1800000000*1000
env['calibration_load_error']='bad record'
assert remaining()==0
for name in ('main.py','laptop_monitor_stop.py'):
    compile((Path(__file__).parent/name).read_text(encoding='utf-8'),name,'exec')
assert 'CAL_LIFETIME_MS' not in source
assert 'calibration_pending.json' not in source
print('PASS: seven-day expiry boundary, restart age, missing clock, future timestamp, invalid record, syntax.')
