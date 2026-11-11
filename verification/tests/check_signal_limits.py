import ast, textwrap
from pathlib import Path
source=(Path(__file__).resolve().parents[2]/'firmware'/'main.py').read_text(encoding='utf-8')
tree=ast.parse(source)
helper=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='signal_out_of_range')
limits=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('ADC_MIN','ADC_MAX') for t in n.targets)]
env={}
exec(compile(ast.Module(body=limits,type_ignores=[]),'limits','exec'),env)
exec(compile(ast.Module(body=[helper],type_ignores=[]),'helper','exec'),env)
start=source.index('        # Collect faults during the timed test')
end=source.index('        ring.fill(OFF if sample_id',start)
override=compile(textwrap.dedent(source[start:end]),'override','exec')
for raw,expected in [(0,True),(499,True),(500,False),(501,False),(45000,False),(59999,False),(60000,False),(60001,True),(65535,True)]:
    assert env['signal_out_of_range'](raw)==expected
    for age in (1000,21000,30000):
        ns=dict(env,fault=expected,ready=age>=21000,sample_id='test',sample_elapsed=age,
                state='NORMAL',verdict='GASTRIC_RANGE',reason='VALID',settled=True,sample_stopped=False)
        exec(override,ns)
        if expected and age>=21000:
            assert ns['verdict'] is None and ns['reason']=='SIGNAL_OUT_OF_RANGE'
            assert ns['sample_stopped'] and not ns['settled']
        else:
            assert not ns['sample_stopped']
print('PASS: inclusive ADC boundaries, results withheld before 21 seconds, fault stop at/after decision.')
