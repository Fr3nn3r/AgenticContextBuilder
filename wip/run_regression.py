# Bootstrap: builds and runs regression risk analysis
import importlib.util, os, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
exec(open(os.path.join(os.path.dirname(__file__), "regression_risk_impl.py"), encoding="utf-8").read())
