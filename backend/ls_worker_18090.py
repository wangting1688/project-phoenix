# -*- coding: utf-8 -*-
import os, importlib.util
os.environ["LIPSYNC_ENGINE"] = "latentsync"
os.environ["LATENTSYNC_REFINE"] = "0"
os.environ["LATENTSYNC_DEEPCACHE"] = "0"
_HERE = os.path.dirname(os.path.abspath(__file__))
GW = os.path.join(_HERE, "gpu_worker.py")
spec = importlib.util.spec_from_file_location("gpu_worker_ls", GW)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import uvicorn
print(">>> LatentSync(no-refine) worker on 127.0.0.1:18090", flush=True)
uvicorn.run(m.app, host="127.0.0.1", port=18090, log_level="info")
