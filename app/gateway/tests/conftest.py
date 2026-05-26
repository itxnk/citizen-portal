import sys
import os

# Ensure this service's directory is on the path before test collection.
# Uses a unique sys.modules key so Prometheus metrics don't collide when
# all services are tested in the same pytest process.
_svc_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _svc_dir not in sys.path:
    sys.path.insert(0, _svc_dir)
