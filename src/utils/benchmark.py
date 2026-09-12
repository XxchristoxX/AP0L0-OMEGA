import time
import psutil
import importlib

def benchmark_skill(skill_name, params):
    try:
        mod = importlib.import_module(f"src.skills.{skill_name}")
        if not hasattr(mod, f"skill_{skill_name}"):
            return None
        start_time = time.time()
        start_cpu = psutil.cpu_percent()
        result = getattr(mod, f"skill_{skill_name}")(params)
        end_time = time.time()
        end_cpu = psutil.cpu_percent()
        return {
            "skill": skill_name,
            "time": end_time - start_time,
            "cpu_usage": end_cpu - start_cpu,
            "result": result
        }
    except Exception as e:
        return {"skill": skill_name, "error": str(e)}
