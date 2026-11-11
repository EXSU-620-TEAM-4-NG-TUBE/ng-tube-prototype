import ast
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import json
source = (Path(__file__).parent/'main.py').read_text(encoding='utf-8')
tree = ast.parse(source)
decide = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name=='decide')
env = {}
exec(compile(ast.Module(body=[decide],type_ignores=[]),'decide','exec'),env)
block = source[source.index('        ready = sample_elapsed'):source.index('        if calibration_valid and sample_id is None:')]
import textwrap
code = compile(textwrap.dedent(block),'deadline','exec')
def check(age, stable, expected, valid=True, fault=False):
    ns = dict(env, sample_elapsed=age, SETTLING_DEADLINE_MS=20000,
              ph=7, settled=stable, calibration_valid=valid, fault=fault,
              deadline_checked=False,sample_stopped=False, sample_id='x',
              elapsed=age, spread=.1, json=json, drift_info=None)
    with redirect_stdout(StringIO()): exec(code,ns)
    assert ns['reason']==expected,ns
    return ns
assert check(19999,True,'NOT_SETTLED')['verdict'] is None
assert check(20000,True,'VALID')['verdict']=='DO_NOT_FEED'
n = check(20000,False,'UNABLE_TO_SETTLE')
assert n['sample_stopped'] and n['verdict'] is None
assert check(20000,True,'CALIBRATION_INVALID',valid=False)['sample_stopped']
assert check(20000,True,'ADC_FAULT',fault=True)['verdict'] is None
print('PASS: no early verdict, stable deadline pass, terminal timeout, calibration and ADC fault precedence.')
