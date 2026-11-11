import ast
from pathlib import Path
source=(Path(__file__).resolve().parents[2]/'software'/'laptop_monitor_stop.py').read_text(encoding='utf-8')
tree=ast.parse(source)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='countdown_text')
env={}
exec(compile(ast.Module(body=[node],type_ignores=[]),'countdown','exec'),env)
f=env['countdown_text']
assert f('MEASURING',None,0,0).startswith('21 s')
for sec in range(22):
    text=f('MEASURING',{'sample_elapsed_ms':0},sec,0)
    assert text.startswith(str(max(0,21-sec))+' s'),(sec,text)
assert 'waiting for result' in f('MEASURING',{'sample_elapsed_ms':20000},15,10)
assert f('NORMAL',{},0,0)=='0 s — result ready'
assert f('STOPPED',{},0,0)=='Timer stopped'
assert 'disconnected' in f('RECONNECTING',None,0,0)
print('PASS: countdown 21 to 0, delayed result, completion, stop and disconnect.')
