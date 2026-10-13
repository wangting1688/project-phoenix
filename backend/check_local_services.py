# -*- coding: utf-8 -*-
import urllib.request, json
def check(name, url, key=None):
    try:
        with urllib.request.urlopen(url, timeout=6) as r:
            data = r.read().decode("utf-8", "replace")
            ok = r.status == 200
            extra = ""
            if key:
                try: extra = "  " + key + "=" + str(json.loads(data).get(key))
                except Exception: pass
            print(f"[{'OK' if ok else '??'}] {name:12} {url}{extra}")
    except Exception as e:
        print(f"[DOWN] {name:12} {url}  ({type(e).__name__})")
print("== Phoenix 本地 GPU 服务状态 ==")
check("ComfyUI", "http://127.0.0.1:8188/system_stats")
check("Worker", "http://127.0.0.1:18080/health")
check("H3", "http://127.0.0.1:18080/h3/health", "comfyui")
