"""code_tool.py — Execute Python code locally"""
import subprocess, sys, tempfile, os

class CodeExecutorTool:
    name = "execute_python"
    description = "Run Python code. INPUT: code string. OUTPUT: stdout/stderr."
    def _run(self, code: str) -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code); tmp = f.name
        try:
            r = subprocess.run([sys.executable, tmp], capture_output=True, text=True, timeout=30)
            out, err = r.stdout.strip(), r.stderr.strip()
            if out and err: return f"OUTPUT:\n{out}\n\nERRORS:\n{err}"
            elif out: return f"OUTPUT:\n{out}"
            elif err: return f"ERROR:\n{err}"
            else: return "Code ran with no output."
        except subprocess.TimeoutExpired: return "ERROR: Timed out after 30 seconds."
        except Exception as e: return f"ERROR: {str(e)}"
        finally:
            try: os.unlink(tmp)
            except: pass
