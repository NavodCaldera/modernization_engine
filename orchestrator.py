import os
import re
import datetime
from celery import Celery, chord, group
import intake
import parser
import cartographer

# ---------------------------------------------------------
# CELERY SYSTEM CONFIGURATION
# ---------------------------------------------------------
celery_app = Celery(
    'modernization_pipeline',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

# ---------------------------------------------------------
# NAMING AUTHORITY (Fixes CLI/API Handoff Inconsistency)
# ---------------------------------------------------------
def generate_enterprise_job_id(repo_url, user_provided_tag=None):
    """Enforces strict naming: [REPO]_[TAG]_[TIMESTAMP] to avoid collisions."""
    repo_name = repo_url.split("/")[-1].replace(".git", "").lower()
    repo_name = re.sub(r'[^a-z0-9]', '_', repo_name)
    
    tag = re.sub(r'[^a-z0-9]', '_', user_provided_tag.lower()) if user_provided_tag else "auto"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    
    return f"{repo_name}_{tag}_{timestamp}"

# ---------------------------------------------------------
# WORKER 1 & 2: INTAKE (NODE 1)
# ---------------------------------------------------------
@celery_app.task(bind=True, max_retries=3, name="dag.intake_and_discovery")
def task_intake_and_discovery(self, github_link, final_job_id):
    print(f"\n>>> [DAG NODE 1] INTAKE & DISCOVERY: {final_job_id}")
    
    # intake.py handles the defensive I/O and manifest generation
    commit_hash = intake.download_safe_photocopy(github_link, final_job_id)
    workspace_dir = os.path.join("workspaces", final_job_id)
    
    inventory = intake.discover_artifacts(workspace_dir)
    intake.generate_manifest(final_job_id, commit_hash, inventory, workspace_dir)

    # Filter for COBOL programs while ignoring previous resolution/normalization attempts
    cobol_files = [item for item in inventory if item["type"] == "COBOL_PROGRAM" 
                   and "_resolved" not in item["file_name"] 
                   and "_normalized" not in item["file_name"]]
    
    return {
        "workspace_dir": workspace_dir, 
        "cobol_files": cobol_files, 
        "job_name": final_job_id
    }

# ---------------------------------------------------------
# WORKER 3: PARALLEL PARSER (NODE 2)
# ---------------------------------------------------------
@celery_app.task(bind=True, max_retries=2, name="dag.parse_single_file")
def task_parse_single_file(self, file_info, workspace_dir):
    """Runs in parallel across CPU cores via Celery Workers."""
    file_name = file_info["file_name"]
    print(f"⚙️ [DAG PARALLEL NODE] Parsing: {file_name}")
    
    # Find the file in the workspace (handles deep folder structures)
    target_path = None
    for root, _, files in os.walk(workspace_dir):
        if file_name in files:
            target_path = os.path.join(root, file_name)
            break

    if not target_path:
        return None

    try:
        # Tier 1-3 Parsing Pipeline
        resolved_path = parser.resolve_copybooks(target_path, workspace_dir)
        dialect = parser.fingerprint_dialect(resolved_path)
        clean_path = parser.normalize_dialect(resolved_path, dialect)
        ast_path = parser.generate_ast_json(clean_path, dialect)
        return ast_path 
    except Exception as e:
        print(f"💥 Failed: {file_name}. Error: {e}")
        # Automatically retry on transient failures (like API timeouts)
        raise self.retry(exc=e, countdown=10)

# ---------------------------------------------------------
# WORKER 4: CARTOGRAPHER (NODE 3)
# ---------------------------------------------------------
@celery_app.task(bind=True, name="dag.cartographer_and_gate")
def task_cartographer_and_gate(self, ast_paths, workspace_dir, job_name):
    """Triggers only after all parallel parsing tasks are complete."""
    print(f"\n>>> [DAG NODE 3] CARTOGRAPHER: Generating decomposition for {job_name}")
    
    # Filter out any failed parsing paths
    valid_paths = [p for p in ast_paths if p]
    
    if valid_paths:
        # cartographer.py handles optimized graph building and dynamic metrics
        report_path = cartographer.generate_service_decomposition(valid_paths, workspace_dir)
        return {
            "status": "AWAITING_GATE_1", 
            "job_id": job_name,
            "report_pdf": report_path
        }
    else:
        return {"status": "FAILED", "error": "Zero ASTs were generated."}

# ---------------------------------------------------------
# THE DAG BUILDER (THE MANAGER)
# ---------------------------------------------------------
@celery_app.task(name="dag.build_chord")
def build_parsing_chord(intake_result):
    """Helper to dynamically generate parallel tasks."""
    workspace_dir = intake_result["workspace_dir"]
    cobol_files = intake_result["cobol_files"]
    job_name = intake_result["job_name"]
    
    # Create the parallel group
    header = [task_parse_single_file.s(f, workspace_dir) for f in cobol_files]
    
    # The 'callback' triggers after all headers finish
    callback = task_cartographer_and_gate.s(workspace_dir, job_name)
    
    return chord(header)(callback)

def start_enterprise_pipeline(github_link, user_tag=None):
    """
    The Entry Point for CLI and API. 
    Enforces naming and initiates the distributed workflow.
    """
    final_job_id = generate_enterprise_job_id(github_link, user_tag)
    
    workflow = (
        task_intake_and_discovery.s(github_link, final_job_id) |
        build_parsing_chord.s() 
    )
    
    result = workflow.apply_async()
    return result, final_job_id

# --- PRODUCTION ENTRY POINT ---
if __name__ == "__main__":
    # We leave this empty to prevent accidental execution.
    # To start the engine, use 'python cli.py' or start the FastAPI server.
    print("--------------------------------------------------")
    print("Mitra/UoM Modernization Orchestrator")
    print("Status: Standby (Awaiting Redis Tasks)")
    print("--------------------------------------------------")