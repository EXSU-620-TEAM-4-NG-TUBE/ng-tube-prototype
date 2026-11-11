import ast
from pathlib import Path
src=(Path(__file__).parent/'main.py').read_text(encoding='utf-8')
tree=ast.parse(src)
n=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='stuck_summary')
env={'STUCK_LIMIT_PH':.10,'STUCK_DURATION_MS':15000}
exec(compile(ast.Module(body=[n],type_ignores=[]),'stuck','exec'),env)
check=env['stuck_summary']
def capture(value=7):
    return {s:dict(filtered_ph=value,actual_ms=s*1000,on_time=True) for s in range(1,21)}
assert check(capture(),7,True)['failed']
assert check(capture(7.1),7,True)['failed']
assert not check(capture(7.101),7,True)['failed']
assert not check(capture(),None,True)['assessed']
assert not check(capture(),7,False)['assessed']
moving=capture();moving[20]['filtered_ph']=7.2
assert not check(moving,7,True)['failed'] # late movement = not stuck
missing=capture();del missing[10]
assert not check(missing,7,True)['assessed']
print('PASS: stuck duration, inclusive ±0.10 boundary, known change, missing baseline, late movement, missing data.')
