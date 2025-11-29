#%%
import os
import glob
import json
import dotenv
import asyncio
import time
from typing import List, Any

from google.adk.agents import Agent, SequentialAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools import google_search

dotenv.load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    os.environ["GOOGLE_API_KEY"] = api_key
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"

MODEL_NAME = "gemini-2.5-flash-lite"
PROJECT_ROOT = os.getcwd()

INPUT_DIR = os.path.join(PROJECT_ROOT, "input")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
MEMORY_DIR = os.path.join(PROJECT_ROOT, "memory")
MEMORY_PATH = os.path.join(MEMORY_DIR, "project_memory.json")
OBS_DIR = os.path.join(PROJECT_ROOT, "observability")

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MEMORY_DIR, exist_ok=True)
os.makedirs(OBS_DIR, exist_ok=True)

print("Project Root:", PROJECT_ROOT)
print("Model:", MODEL_NAME)

#%%
def read_file_tool(path: str):
    abs_path = os.path.join(PROJECT_ROOT, path)
    if not os.path.exists(abs_path):
        return {"error": f"File not found: {path}"}
    with open(abs_path, "r", encoding="utf-8") as f:
        return {"path": path, "content": f.read()}

def write_file_tool(path: str, content: str):
    abs_path = os.path.join(PROJECT_ROOT, path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"status": "OK", "path": path}

def load_persistent_memory():
    if os.path.exists(MEMORY_PATH):
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# --- Observability (Day 4a) ---
async def observe_run(runner: InMemoryRunner, payload: Any, run_label: str):
    """Runs an agent with logging (Observability)."""
    start = time.time()
    # Ensure payload is a string for run_debug
    payload_str = json.dumps(payload) if not isinstance(payload, str) else payload
    
    print(f"\n[OBSERVABILITY] Starting {run_label}...")
    try:
        result = await runner.run_debug(payload_str)
    except Exception as e:
        result = f"ERROR: {str(e)}"
        print(f"[OBSERVABILITY] Error in {run_label}: {e}")
    
    duration = time.time() - start
    
    log_entry = {
        "timestamp": time.time(),
        "label": run_label,
        "duration_sec": duration,
        "payload_summary": str(payload)[:500],
        "result_summary": str(result)[:500]
    }
    
    log_path = os.path.join(OBS_DIR, "logs.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")
    
    print(f"[OBSERVABILITY] Finished {run_label} in {duration:.2f}s")
    return result

#%%
project_scanner_agent = Agent(
    name="Project_Scanner",
    model=MODEL_NAME,
    description="Scans all .xhtml pages to build global project memory.",
    instruction=r"""
    You will scan multiple JSF .xhtml pages.

    IMPORTANT:
    In this instruction, JSF expressions are written using ${...} to avoid template substitution.
    But in the REAL files you load via read_file_tool, the syntax will be #{...}.
    Treat BOTH the same way.

    INPUT:
    A JSON array of file paths.

    TASKS:
    - Use read_file_tool to load each file
    - Extract:
        • bean references (look for "#{...}" in the file)
        • dataTables
        • dialogs
        • forms
        • repeated components
        • CSS classes
        • title/header/navigation patterns

    OUTPUT JSON:
    {
      "global_beans": [...],
      "global_tables": [...],
      "global_dialogs": [...],
      "common_components": [...],
      "styles": [...]
    }
    """,
    tools=[read_file_tool],
    output_key="project_memory"
)

#%%
memory_persistor_agent = Agent(
    name="Memory_Persistor",
    model=MODEL_NAME,
    description="Writes project-wide memory to disk.",
    instruction=r"""
    Take project memory from [[project_memory]].
    Convert it to JSON.
    Save to: memory/project_memory.json using write_file_tool.
    """,
    tools=[write_file_tool],
    output_key="memory_saved"
)

#%%
jsf_logic_agent = Agent(
    name="JSF_Logic_Extractor",
    model=MODEL_NAME,
    instruction=r"""
    You extract JSF logic from an .xhtml file.

    IMPORTANT:
    In this instruction, JSF EL uses ${...}.
    In the REAL file you read, it will be #{...}.
    Treat both ${...} and #{...} as EL expressions.

    INPUT JSON:
    {
        "file_path": "...",
        "project_memory": <memory object>
    }

    Extract:
    - EL expressions (#{...})
    - bean method calls (action=, actionListener=)
    - data table bindings
    - form bindings
    - validation rules
    - update/process (AJAX rules)
    - conditional rendering

    OUTPUT JSON:
    { "logic_report": ... }
    """,
    tools=[read_file_tool],
    output_key="logic_report"
)

#%%
jsf_visual_agent = Agent(
    name="JSF_Visual_Extractor",
    model=MODEL_NAME,
    instruction=r"""
    You extract UI structure from a JSF file.

    IMPORTANT RULES:
    - The ONLY tool you are allowed to call is read_file_tool.
    - DO NOT call any other tool.
    - DO NOT invent functions such as 'extract_ui_structure', 'parse_dom', etc.
    - You must simply read the file and analyze its text.

    INPUT JSON:
    {
        "file_path": "...",
        "project_memory": [[project_memory]]
    }

    Extract (BY READING THE TEXT YOURSELF):
    - layout blocks (panelGrid, div, panelGroup)
    - dialogs
    - dataTables
    - buttons
    - CSS classes
    - inline styles
    - structure hierarchy

    Then output JSON:
    {
      "visual_report": { ... }
    }

    AGAIN: Use ONLY read_file_tool. DO NOT call any invented tools.
    """,
    tools=[read_file_tool],
    output_key="visual_report"
)

#%%
# Updated Angular Architect with Google Search (Mod 4)
angular_architect_agent = Agent(
    name="Angular_Architect",
    model=MODEL_NAME,
    instruction=r"""
    You combine:
      - project memory: [[project_memory]]
      - logic: [[logic_report]]
      - visuals: [[visual_report]]

    Produce an Angular migration blueprint:
      - component name
      - Angular Material equivalents
      - services needed
      - routing path
      - shared components
      - form structure
      - table/dialog mappings

    IMPORTANT:
    - If you encounter a JSF component and are unsure of its Angular equivalent, use the 'google_search' tool to find the best match.
    - Example query: "PrimeFaces p:dataTable Angular Material equivalent"

    OUTPUT MUST BE JSON.
    """,
    tools=[google_search], # Added google_search
    output_key="migration_blueprint"
)

#%%
angular_codegen_agent = Agent(
    name="Angular_Code_Generator",
    model=MODEL_NAME,
    instruction=r"""
    Input: [[migration_blueprint]]

    Generate:
      - component.ts
      - component.html
      - component.css
      - service.ts

    Use write_file_tool to save them under output/<component-name>/.

    Output JSON list of created files.
    """,
    tools=[write_file_tool],
    output_key="generated_files"
)

#%%
# Added Evaluation Agent (Day 4b)
evaluation_agent = Agent(
    name="Migration_Evaluator",
    model=MODEL_NAME,
    instruction=r"""
    INPUTS: [[migration_blueprint]], [[generated_files]], [[project_memory]]
    
    TASK: Evaluate the quality of the migration.
    - Check Structural Completeness (Are all components present?)
    - Check Mapping Accuracy (Do bindings match?)
    - Check Style/Best Practices.
    
    OUTPUT JSON:
    {
      "evaluation_report": {
        "score": 0.0-10.0,
        "issues": [...],
        "recommendations": [...]
      }
    }
    """,
    output_key="evaluation_report"
)

#%%
bootstrap_pipeline = SequentialAgent(
    name="Bootstrap",
    sub_agents=[
        project_scanner_agent,
        memory_persistor_agent
    ]
)

#%%
migration_pipeline = SequentialAgent(
    name="Migration",
    sub_agents=[
        jsf_logic_agent,
        jsf_visual_agent,
        angular_architect_agent,
        angular_codegen_agent,
        evaluation_agent # Added Evaluator
    ]
)

#%%
bootstrap_runner = InMemoryRunner(agent=bootstrap_pipeline)
migration_runner = InMemoryRunner(agent=migration_pipeline)

async def run_all():
    files = glob.glob(os.path.join(INPUT_DIR, "*.xhtml"))
    if not files:
        print("⚠ No XHTML files found.")
        return

    rel_files = [os.path.relpath(f, PROJECT_ROOT) for f in files]

    print("\n🔍 BUILDING PROJECT MEMORY…")
    # Use observe_run for Bootstrap
    await observe_run(bootstrap_runner, rel_files, "Bootstrap")

    project_memory = load_persistent_memory()
    print("\n🧠 Loaded Project Memory")

    print("\n🚀 MIGRATING PAGES…")
    for f in files:
        rel = os.path.relpath(f, PROJECT_ROOT)
        print(f"\n--- Migrating {rel} ---")
        
        payload = {
            "file_path": rel,
            "project_memory": project_memory
        }
        
        # Use observe_run for Migration
        await observe_run(migration_runner, payload, f"Migration:{rel}")
        
        print("  -> Waiting 5 seconds to respect API quota...")
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run_all())
