# Software verification tests

Install the monitor dependencies from [requirements.txt](../../software/browser_monitor/requirements.txt). From the repository root, run:

```text
python -m unittest discover -s verification/tests
```

The `check_*.py` scripts are standalone checks. Run each with Python from the repository root. The current notification tests use a mock provider. See the [final report](../../docs/EXSU620_Team4_Final_Report.pdf) for bench evidence and remaining live verification.
