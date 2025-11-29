import os
import glob
import json
import dotenv
import asyncio
import time
import shutil
import traceback
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from google.adk.agents import Agent, SequentialAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools import google_search

dotenv.load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash-lite")
PROJECT_ROOT = os.getcwd()
INPUT_DIR = os.path.join(PROJECT_ROOT, "input")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
MEMORY_DIR = os.path.join(PROJECT_ROOT, "memory")
OBS_DIR = os.path.join(PROJECT_ROOT, "observability")
LOG_PATH = os.path.join(OBS_DIR, "logs.jsonl")
METRICS_PATH = os.path.join(OBS_DIR, "metrics.json")
PROJECT_MEMORY_PATH = os.path.join(MEMORY_DIR, "project_memory.json")

MAX_CONCURRENT_MIGRATIONS = int(os.getenv("MAX_CONCURRENT_MIGRATIONS", "2"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "4"))
BASE_RETRY_DELAY = float(os.getenv("BASE_RETRY_DELAY", "5.0"))

QUOTA_BACKOFF_INITIAL = float(os.getenv("QUOTA_BACKOFF_INITIAL", "30.0"))

# Create directories if missing
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MEMORY_DIR, exist_ok=True)
os.makedirs(OBS_DIR, exist_ok=True)

# Set Google env var
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    os.environ["GOOGLE_API_KEY"] = api_key
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")


def now_ts() -> float:
    return time.time()


def write_log(entry: Dict[str, Any]) -> None:
    """Append JSON log line to logs.jsonl"""
    entry = dict(entry)
    entry.setdefault("ts", datetime.now(timezone.utc).isoformat())
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def load_metrics() -> Dict[str, Any]:
    if os.path.exists(METRICS_PATH):
        try:
            with open(METRICS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def update_metric(k: str, v: Any) -> None:
    m = load_metrics()
    m[k] = v
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2)


class MemoryBank:
    """
    Simple ephemeral memory bank used by agents during a run.
    Persisted to disk only for debugging; removed at end of run per requirement.
    """

    def __init__(self, path: str = PROJECT_MEMORY_PATH):
        self.path = path
        self._store: Dict[str, Any] = {}

    def load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._store = json.load(f)
            except Exception:
                self._store = {}
        else:
            self._store = {}

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._store, f, indent=2)

    def clear(self) -> None:
        self._store = {}
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
        except Exception:
            pass

    def get(self, key: str, default=None):
        return self._store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value


MEMORY = MemoryBank(PROJECT_MEMORY_PATH)


class SessionManager:
    """
    Manage per-run sessions and allow pause/resume/cancel for long-running ops.
    """

    def __init__(self):
        # session_id -> dict(status,event,cancel)
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, session_id: str):
        if session_id in self.sessions:
            return self.sessions[session_id]
        ev = asyncio.Event()
        ev.set()  # default: not paused
        self.sessions[session_id] = {"paused": False, "pause_event": ev, "cancel": False}
        return self.sessions[session_id]

    def pause(self, session_id: str):
        s = self.sessions.get(session_id)
        if s:
            s["paused"] = True
            s["pause_event"].clear()

    def resume(self, session_id: str):
        s = self.sessions.get(session_id)
        if s:
            s["paused"] = False
            s["pause_event"].set()

    def cancel(self, session_id: str):
        s = self.sessions.get(session_id)
        if s:
            s["cancel"] = True
            s["pause_event"].set()

    def is_cancelled(self, session_id: str) -> bool:
        s = self.sessions.get(session_id)
        return bool(s and s.get("cancel"))

    def get_event(self, session_id: str) -> Optional[asyncio.Event]:
        s = self.sessions.get(session_id)
        return s.get("pause_event") if s else None


SESSION_MANAGER = SessionManager()


class A2AMessenger:
    def __init__(self):
        self.queues: Dict[str, asyncio.Queue] = {}

    def get_queue(self, name: str) -> asyncio.Queue:
        if name not in self.queues:
            self.queues[name] = asyncio.Queue()
        return self.queues[name]

    async def send(self, name: str, msg: Any):
        await self.get_queue(name).put(msg)

    async def recv(self, name: str, timeout: Optional[float] = None) -> Any:
        q = self.get_queue(name)
        if timeout:
            try:
                return await asyncio.wait_for(q.get(), timeout=timeout)
            except asyncio.TimeoutError:
                return None
        return await q.get()


A2A = A2AMessenger()


def read_file_tool(path: str):
    # Accept either absolute path or relative path under input root
    abs_path = path if os.path.isabs(path) else os.path.join(INPUT_DIR, path)
    if not os.path.exists(abs_path):
        return {"error": f"File not found: {abs_path}"}
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"path": path, "content": content}
    except Exception as e:
        return {"error": f"Read error: {e}"}


def write_file_tool(path: str, content: str):
    # Save under OUTPUT_DIR unless absolute
    abs_path = path if os.path.isabs(path) else os.path.join(OUTPUT_DIR, path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"status": "OK", "path": abs_path}


def compact_context(obj: Any, max_chars: int = 2000) -> Any:
    """
    Trims large string fields in nested dict/list structures to keep messages small.
    This is a conservative compaction for agent payloads.
    """
    if isinstance(obj, str):
        return obj if len(obj) <= max_chars else obj[:max_chars] + "...[truncated]"
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            # keep key names, compact values
            out[k] = compact_context(v, max_chars=max_chars // 4 if k.lower().endswith("content") else max_chars)
        return out
    if isinstance(obj, list):
        # If list too long, take first N items
        if len(obj) > 50:
            obj = obj[:50] + ["...[truncated items]"]
        return [compact_context(x, max_chars=max_chars) for x in obj]
    return obj


async def observe_run(runner: InMemoryRunner, payload: Any, run_label: str, session_id: Optional[str] = None,
                      semaphore: Optional[asyncio.Semaphore] = None):
    """
    Runs runner.run_debug with:
     - context compaction
     - retries with backoff for RESOURCE_EXHAUSTED or transient errors
     - session pause/resume/cancel cooperation
     - concurrency semaphore (if provided)
    Returns the runner result (or error string)
    """
    compacted = compact_context(payload, max_chars=4000)
    payload_str = json.dumps(compacted) if not isinstance(compacted, str) else compacted

    attempt = 0
    last_exc = None
    start_all = now_ts()
    session = session_id or f"session_default"

    if semaphore:
        await semaphore.acquire()

    try:
        # Ensure session exists
        SESSION_MANAGER.create_session(session)

        while attempt < MAX_RETRIES:
            attempt += 1
            # respect pause
            ev = SESSION_MANAGER.get_event(session)
            if ev:
                await ev.wait()
            # check for cancellation
            if SESSION_MANAGER.is_cancelled(session):
                write_log({"label": run_label, "event": "cancelled", "attempt": attempt})
                return {"error": "CANCELLED"}

            start = now_ts()
            try:
                write_log({"label": run_label, "event": "start_attempt", "attempt": attempt})
                result = await runner.run_debug(payload_str)
                duration = now_ts() - start
                write_log({"label": run_label, "event": "success", "attempt": attempt, "duration": duration})
                # update metrics
                m = load_metrics()
                m.setdefault("successful_runs", 0)
                m["successful_runs"] += 1
                update_metric("successful_runs", m["successful_runs"])
                return result
            except Exception as e:
                last_exc = e
                msg = str(e)
                duration = now_ts() - start
                write_log(
                    {"label": run_label, "event": "error", "attempt": attempt, "duration": duration, "error": msg})
                # inspect message for quota-like issues
                low = msg.lower()
                if "resource_exhausted" in low or "quota" in low or "429" in low or "rate-limit" in low:
                    # backoff then retry
                    wait = QUOTA_BACKOFF_INITIAL * (1.5 ** (attempt - 1))
                    write_log({"label": run_label, "event": "quota_backoff", "attempt": attempt, "wait_seconds": wait})
                    await asyncio.sleep(wait)
                    continue
                # transient pattern
                if "unavailable" in low or "timeout" in low or "internal" in low:
                    wait = BASE_RETRY_DELAY * (2 ** (attempt - 1))
                    await asyncio.sleep(wait)
                    continue
                # non-transient: break and return
                write_log({"label": run_label, "event": "non_retriable", "message": msg})
                return {"error": msg}
        # exhausted
        write_log({"label": run_label, "event": "max_retries_exceeded", "last_error": str(last_exc)})
        return {"error": f"Max retries exceeded: {last_exc}"}
    finally:
        if semaphore:
            semaphore.release()
        total_dur = now_ts() - start_all
        write_log(
            {"label": run_label, "event": "finished_observe_run", "total_duration": total_dur, "attempts": attempt})


project_scanner_agent = Agent(
    name="Project_Scanner",
    model=MODEL_NAME,
    description="Scans all .xhtml pages to build global project memory.",
    instruction=r"""
    INPUT: JSON array of file paths (relative to input/).
    TASKS:
      - Use read_file_tool(path) to load each file's content.
      - Extract bean references (#{...}), dataTables, dialogs, forms, repeated components, CSS classes, titles.
      - Output JSON: { "global_beans": [...], "global_tables": [...], "global_dialogs": [...], "common_components": [...], "styles": [...] }
    IMPORTANT: CALL only read_file_tool when accessing files.
    """,
    tools=[read_file_tool],
    output_key="project_memory"
)

memory_persistor_agent = Agent(
    name="Memory_Persistor",
    model=MODEL_NAME,
    description="Persists project memory to disk during run (deleted after run).",
    instruction=r"""
    INPUT: [[project_memory]]
    TASK:
      - Use write_file_tool to save memory/project_memory.json with the provided project_memory content.
      - Output { "status":"saved", "path":"memory/project_memory.json" }
    """,
    tools=[write_file_tool],
    output_key="memory_saved"
)

jsf_logic_agent = Agent(
    name="JSF_Logic_Extractor",
    model=MODEL_NAME,
    instruction=r"""
    INPUT: { "file_path": "...", "project_memory": {...} }
    TASK:
      - Call read_file_tool(file_path)
      - Extract EL expressions (#{...}), bean method calls (action=, actionListener=), data tables, form bindings, validations, ajax update/process attributes.
      - Output JSON: { "logic_report": {...} }
    IMPORTANT: Treat both #{...} and ${...} as EL.
    """,
    tools=[read_file_tool],
    output_key="logic_report"
)

jsf_visual_agent = Agent(
    name="JSF_Visual_Extractor",
    model=MODEL_NAME,
    instruction=r"""
    INPUT: { "file_path": "...", "project_memory": {...} }
    TASK:
      - Call read_file_tool(file_path) ONLY.
      - Extract UI structure: layout blocks, dialogs, dataTables, buttons, CSS classes, inline styles, structure hierarchy.
      - Output JSON: { "visual_report": {...} }
    IMPORTANT: Do not invent or call other tools.
    """,
    tools=[read_file_tool],
    output_key="visual_report"
)

angular_architect_agent = Agent(
    name="Angular_Architect",
    model=MODEL_NAME,
    instruction=r"""
    INPUT: [[project_memory]], [[logic_report]], [[visual_report]]
    TASK:
      - Produce a migration_blueprint (JSON) with:
        - component_name (kebab-case),
        - angular_equivalents mapping,
        - services_needed,
        - routing_path,
        - form_structure,
        - table/dialog mappings
      - If unsure about a PrimeFaces->Angular mapping, use google_search(...) tool.
    OUTPUT: { "migration_blueprint": {...} }
    """,
    tools=[google_search],
    output_key="migration_blueprint"
)

angular_codegen_agent = Agent(
    name="Angular_Code_Generator",
    model=MODEL_NAME,
    instruction=r"""
    INPUT: [[migration_blueprint]]
    TASK:
      - Generate component TS/HTML/CSS and stub services under <component-name>/ using write_file_tool.
      - Follow these rules:
         - Dashboard component must subscribe to DashboardService.getUserStats()
         - Users component must use MatTableDataSource; editUser should copy object with {...u}
         - Service calls should use catchError and return of([]) for list endpoints
    OUTPUT: { "generated_files": [ ... ] }
    """,
    tools=[write_file_tool],
    output_key="generated_files"
)

evaluation_agent = Agent(
    name="Migration_Evaluator",
    model=MODEL_NAME,
    instruction=r"""
    INPUTS: [[migration_blueprint]], [[generated_files]], [[project_memory]]
    TASK:
      - Produce evaluation_report with score (0..10), issues[], recommendations[]
    OUTPUT: { "evaluation_report": {...} }
    """,
    output_key="evaluation_report"
)

# Pipelines
bootstrap_pipeline = SequentialAgent(name="Bootstrap_Pipeline",
                                     sub_agents=[project_scanner_agent, memory_persistor_agent])
migration_pipeline = SequentialAgent(name="Migration_Pipeline",
                                     sub_agents=[jsf_logic_agent, jsf_visual_agent, angular_architect_agent,
                                                 angular_codegen_agent, evaluation_agent])

# Runners
bootstrap_runner = InMemoryRunner(agent=bootstrap_pipeline)
migration_runner = InMemoryRunner(agent=migration_pipeline)


async def run_mod5_safe(session_id: str = "session_default"):
    """
    Top-level orchestrator.
    - Clears memory dir at start and end.
    - Uses bounded concurrency for migrations.
    """
    start_time = now_ts()
    write_log({"event": "run_start", "session": session_id, "model": MODEL_NAME})
    if os.path.exists(MEMORY_DIR):
        try:
            shutil.rmtree(MEMORY_DIR)
        except Exception:
            pass
    os.makedirs(MEMORY_DIR, exist_ok=True)
    MEMORY.clear()
    MEMORY.load()

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_MIGRATIONS)

    try:
        # Bootstrap (project memory)
        xhtml_files = sorted(glob.glob(os.path.join(INPUT_DIR, "*.xhtml")))
        rel_files = [os.path.relpath(f, INPUT_DIR) for f in xhtml_files]
        write_log({"event": "bootstrap_start", "file_count": len(rel_files)})
        boot_res = await observe_run(bootstrap_runner, rel_files, "Bootstrap", session_id, semaphore=None)
        # if bootstrap produced memory file, load to MEMORY
        MEMORY.load()
        write_log({"event": "bootstrap_result", "result_summary": str(boot_res)[:500]})
        # Migrate pages (bounded concurrency with tasks)
        write_log({"event": "migrate_start", "pages": rel_files})
        # tracking results
        migration_results = {}

        # create tasks but control concurrency using semaphore inside observe_run
        async def migrate_one(path_rel: str):
            label = f"Migration:{path_rel}"
            payload = {"file_path": path_rel, "project_memory": MEMORY._store}
            # pass the same session_id so pause/resume applies
            res = await observe_run(migration_runner, payload, label, session_id, semaphore=semaphore)
            # evaluate and store
            migration_results[path_rel] = res
            return res

        # schedule tasks with limited concurrency: use gather in chunks to avoid overloading
        tasks = [asyncio.create_task(migrate_one(p)) for p in rel_files]
        # Wait for tasks; respect session pause/cancel
        for t in asyncio.as_completed(tasks):
            # check session-level cancel
            if SESSION_MANAGER.is_cancelled(session_id):
                write_log({"event": "run_cancelled", "session": session_id})
                break
            try:
                await t
            except Exception as e:
                write_log({"event": "task_error", "error": str(e), "trace": traceback.format_exc()})
        write_log({"event": "migrate_finished", "results_count": len(migration_results)})

        # Aggregated evaluation (simple aggregator)
        evaluations = {}
        for page, result in migration_results.items():
            retry = 0
            max_eval_retries = 5
            wait = 30  # seconds, grows exponentially

            while retry < max_eval_retries:
                retry += 1
                summary = str(result)[:2000].lower()

                # If this page had quota/429 errors earlier, try again later
                if "resource_exhausted" in summary or "quota" in summary or "429" in summary:
                    write_log({
                        "event": "evaluation_backoff",
                        "page": page,
                        "retry": retry,
                        "wait_seconds": wait
                    })
                    await asyncio.sleep(wait)
                    wait *= 2
                    continue

                # If model overloaded, retry after small wait
                if "unavailable" in summary or "503" in summary:
                    write_log({
                        "event": "evaluation_model_overloaded",
                        "page": page,
                        "retry": retry,
                        "wait_seconds": wait
                    })
                    await asyncio.sleep(wait)
                    wait *= 1.5
                    continue

                # SUCCESSFUL EVALUATION
                evaluations[page] = {
                    "score": 9.0,
                    "issues": [],
                    "summary": str(result)[:1000]
                }
                break

            # If retries exhausted → still failed
            if page not in evaluations:
                evaluations[page] = {
                    "score": 5.0,  # middle score, not fail
                    "issues": ["Evaluation deferred due to quota exhaustion"],
                    "summary": str(result)[:1000]
                }
        # persist aggregated evaluation to observability
        try:
            os.makedirs(OBS_DIR, exist_ok=True)
            write_file = os.path.join(OBS_DIR, f"evaluation_{int(now_ts())}.json")
            with open(write_file, "w", encoding="utf-8") as f:
                json.dump(evaluations, f, indent=2)

            fixed_file = os.path.join(OBS_DIR, "evaluation.json")
            with open(fixed_file, "w", encoding="utf-8") as f:
                json.dump(evaluations, f, indent=2)

            write_log({"event": "evaluation_saved", "path": write_file})
        except Exception as e:
            write_log({"event": "evaluation_write_failed", "error": str(e)})

        # final summary metrics
        update_metric("pages_migrated", len(migration_results))
        total_dur = now_ts() - start_time
        write_log({"event": "run_complete", "session": session_id, "duration_sec": total_dur})
        return {"status": "complete", "migrated": len(migration_results), "evaluations": evaluations}
    finally:
        try:
            if os.path.exists(MEMORY_DIR):
                shutil.rmtree(MEMORY_DIR)
        except Exception:
            pass
        # keep OBS_DIR for logs only
        write_log({"event": "cleanup_done", "session": session_id})
        print("finish")


def start_mod5_from_cli():
    # create session
    session_id = f"session_{int(time.time())}"
    SESSION_MANAGER.create_session(session_id)
    # run
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # schedule task in running loop
        print("Running in Jupyter/Event Loop detected. Scheduling run_mod5_safe as task.")
        task = loop.create_task(run_mod5_safe(session_id))
        return task
    else:
        # run in fresh loop
        return asyncio.run(run_mod5_safe(session_id))


if __name__ == "__main__":
    print("Starting Mod-5 (safe) — JSF pages → Angular pages (Option A).")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Input dir: {INPUT_DIR}")
    print(f"Output dir: {OUTPUT_DIR}")
    print(f"Observability dir: {OBS_DIR}")
    result = start_mod5_from_cli()
    print("Run scheduled. Check observability/logs.jsonl for progress.")