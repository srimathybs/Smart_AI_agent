# Smart AI Agent v2
## 100% Free · No API Key · All Features · Runs Locally

### Features
- Any file input: PDF, DOCX, CSV, Excel, images, code files, text
- 6 AI models: TinyLlama, Phi-3, Mistral, Llama3.2, CodeLlama, LLaVA
- Persistent memory (ChromaDB)
- Web search + URL scraper (DuckDuckGo, free)
- Python code execution
- Math solver (sympy exact answers)
- Chart generator (Plotly)
- SQL database with sample data
- Text-to-speech in 14 languages
- Export to PDF and Word DOCX
- Streaming responses
- Long detailed answers
- User profiles (separate memory per user)
- Monitoring dashboard
- Session history with download

### Setup

STEP 1 - Install Python 3.11
  python.org/downloads/release/python-3119/
  TICK: Add Python to PATH

STEP 2 - Install Ollama
  ollama.com -> Download for Windows
  Then: ollama pull tinyllama

STEP 3 - Open in VS Code
  Unzip -> File -> Open Folder -> select smart-agent-v2/
  Open terminal: Ctrl + `

STEP 4 - Create venv
  python -m venv venv
  venv\Scripts\activate

STEP 5 - Install libraries
  pip install -r requirements.txt

STEP 6 - Start Ollama (KEEP OPEN)
  ollama serve

STEP 7 - Run app
  streamlit run app.py

Browser opens at: http://localhost:8501

### Every session: 3 commands
  Terminal 1: ollama serve
  VS Code:    venv\Scripts\activate
              streamlit run app.py

### Models
  ollama pull tinyllama   (637 MB - fastest)
  ollama pull phi3        (2.2 GB - coding)
  ollama pull mistral     (4.1 GB - best quality)
  ollama pull codellama   (3.8 GB - Python expert)
  ollama pull llava       (4.5 GB - image vision)
