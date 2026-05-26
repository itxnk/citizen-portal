import sys
import os

_svc_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _svc_dir not in sys.path:
    sys.path.insert(0, _svc_dir)
