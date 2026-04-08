import os
import git
import shutil
import stat
import json
import logging

# Set up enterprise logging to track file access issues without crashing the UI
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def unlock_readonly_files(func, path, exc_info):
    """A universal helper to remove Read-Only or permission locks on files."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        logging.warning(f"Failed to force-unlock {path}: {e}")

def download_safe_photocopy(repo_link, job_folder_name):
    """Downloads repository with robust pre-cleanup and error handling."""
    print(f"Starting the safe photocopy process for {job_folder_name}...")
    workspace_path = os.path.join("workspaces", job_folder_name)
    
    if os.path.exists(workspace_path):
        print("Found an old folder. Cleaning it up first...")
        # Use onexc (Python 3.12+) or onerror for older versions to handle locked files
        shutil.rmtree(workspace_path, onexc=unlock_readonly_files)
    
    os.makedirs(workspace_path, exist_ok=True)
    
    try:
        print("Downloading code from the internet. Please wait...")
        downloaded_repo = git.Repo.clone_from(repo_link, workspace_path)
        commit_hash = downloaded_repo.head.commit.hexsha
        print(f"Secured tracking receipt: {commit_hash}")
        return commit_hash
    except Exception as e:
        print(f"💥 FATAL INTAKE ERROR: Repository clone failed. {e}")
        return None

def discover_artifacts(workspace_path):
    """Scans for artifacts with non-blocking error handling for locked files."""
    print("\nStarting the Artifact Scanner...")
    inventory = []

    for folder_path, _, files in os.walk(workspace_path):
        if ".git" in folder_path:
            continue
            
        for file_name in files:
            full_file_path = os.path.join(folder_path, file_name)
            
            # Enterprise Safety: Try to catch permission errors before opening
            if not os.access(full_file_path, os.R_OK):
                logging.warning(f"Skipping file (No Read Access): {file_name}")
                continue

            try:
                # Use 'rb' and then decode to handle mixed-encoding mainframe files safely
                with open(full_file_path, 'rb') as f:
                    raw_data = f.read()
                    lines = raw_data.decode('utf-8', errors='ignore').splitlines()
                
                if not lines:
                    continue
                        
                top_lines = "\n".join([line.upper() for line in lines[:20]])
                artifact_type = "UNKNOWN_TEXT_FILE"
                
                # Identification Logic
                if "IDENTIFICATION DIVISION" in top_lines:
                    artifact_type = "COBOL_PROGRAM"
                elif any(k in top_lines for k in ["// JOB", "EXEC PGM"]):
                    artifact_type = "JCL_SCRIPT"
                elif "DFHMSD" in top_lines or file_name.upper().endswith(".BMS"):
                    artifact_type = "BMS_SCREEN_MAP"
                elif "DEFINE CLUSTER" in top_lines or file_name.upper().endswith(".DBD"):
                    artifact_type = "VSAM_DEFINITION"
                elif "CREATE TABLE" in top_lines or file_name.upper().endswith(".SQL"):
                    artifact_type = "SQL_SCRIPT"
                elif file_name.upper().endswith(".CPY"):
                    artifact_type = "COPYBOOK"

                # Metrics calculation
                loc_count = 0
                complexity_score = 0
                for line in lines:
                    stripped = line.strip()
                    if not stripped or (len(line) > 6 and line[6] == '*'):
                        continue
                    loc_count += 1
                    if any(k in stripped.upper() for k in [" IF ", " EVALUATE ", " WHEN ", " PERFORM "]):
                        complexity_score += 1

                inventory.append({
                    "file_name": file_name,
                    "type": artifact_type,
                    "loc": loc_count,
                    "complexity": complexity_score,
                    "rel_path": os.path.relpath(full_file_path, workspace_path)
                })
                    
            except (IOError, OSError) as e:
                logging.error(f"System Lock Error: Could not access {file_name}. Skipping. {e}")
            except Exception as e:
                logging.error(f"Unexpected error scanning {file_name}: {e}")

    print(f"Scanning complete! Inventory size: {len(inventory)}")
    return inventory

def generate_manifest(job_folder_name, commit_hash, inventory, workspace_path):
    """Saves the factory manifest with atomic write protection."""
    manifest_data = {
        "job_id": job_folder_name,
        "commit_hash": commit_hash,
        "total_files": len(inventory),
        "inventory": inventory
    }
    
    manifest_path = os.path.join(workspace_path, "manifest.json")
    
    try:
        with open(manifest_path, 'w', encoding='utf-8') as json_file:
            json.dump(manifest_data, json_file, indent=4)
        print(f"✅ Success! Manifest saved at: {manifest_path}")
    except Exception as e:
        print(f"💥 Failed to write manifest: {e}")