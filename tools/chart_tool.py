"""chart_tool.py — Generate interactive Plotly charts"""
import json, os

class ChartTool:
    name = "create_chart"
    description = "Create a chart. INPUT: JSON with keys: type(bar/line/pie/scatter), title, labels(list), values(list). OUTPUT: path to HTML chart file."
    def _run(self, chart_json: str) -> str:
        try:
            import plotly.graph_objects as go
            data = json.loads(chart_json) if isinstance(chart_json, str) else chart_json
            t    = data.get("type","bar").lower()
            title  = data.get("title","Chart")
            labels = data.get("labels",[])
            values = data.get("values",[])
            if t == "bar":
                fig = go.Figure(go.Bar(x=labels, y=values, text=values, textposition="auto"))
            elif t == "line":
                fig = go.Figure(go.Scatter(x=labels, y=values, mode="lines+markers"))
            elif t == "pie":
                fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.3))
            else:
                fig = go.Figure(go.Scatter(x=labels, y=values, mode="markers"))
            fig.update_layout(title=title, template="plotly_white", height=400)
            os.makedirs("outputs", exist_ok=True)
            path = f"outputs/chart_{abs(hash(title))}.html"
            fig.write_html(path)
            return f"CHART_SAVED:{path}"
        except ImportError: return "ERROR: pip install plotly"
        except Exception as e: return f"Chart error: {str(e)}"
