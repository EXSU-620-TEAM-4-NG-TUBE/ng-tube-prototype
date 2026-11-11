import ast
from pathlib import Path
source = (Path(__file__).parent/'main.py').read_text(encoding='utf-8')
tree = ast.parse(source)
node = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='drift_summary')
env = {'DRIFT_LIMIT_PH':.4}
exec(compile(ast.Module(body=[node],type_ignores=[]),'drift','exec'),env)
check = env['drift_summary']
assert not check([4]*3,[4.4]*3,6)['failed']
assert check([4]*3,[4.401]*3,6)['failed']
assert check([7]*3,[6.599]*3,6)['failed']
assert not check([4]*3,[4]*3,6)['failed']
assert check([4]*3,[4,4,5.5],6)['failed']  # A jump can trigger the user's rule.
assert check([4]*3,[4]*3,5) is None
assert check([23]*3,[4]*3,6) is None
for file in ('main.py','laptop_monitor_stop.py'):
    compile((Path(__file__).parent/file).read_text(encoding='utf-8'),file,'exec')
print('PASS: drift boundaries, both directions, isolated jump, insufficient data, invalid values, syntax.')
