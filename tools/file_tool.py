"""file_tool.py — Read and write files on disk"""
import os

class FileReadTool:
    name = "read_file"
    description = "Read a file. INPUT: file path. OUTPUT: file content."
    def _run(self, path: str) -> str:
        try:
            if not os.path.exists(path): return f"ERROR: File not found at '{path}'"
            with open(path, "r", encoding="utf-8") as f: return f.read(6000)
        except Exception as e: return f"ERROR: {str(e)}"

class FileWriteTool:
    name = "write_file"
    description = "Save content to a file. INPUT: path and content. OUTPUT: confirmation."
    def _run(self, path: str, content: str = "") -> str:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f: f.write(content)
            return f"Saved to: {os.path.abspath(path)}"
        except Exception as e: return f"ERROR: {str(e)}"
