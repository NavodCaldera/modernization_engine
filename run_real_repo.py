import os
import subprocess
import glob
import parser
import cartographer

def run_real_world_analysis():
    print("==================================================")
    print("🌍 INITIATING REAL-WORLD REPOSITORY ANALYSIS")
    print("==================================================")

    # 1.Target the AWS Mainframe Modernization Repo
    repo_url = "https://github.com/aws-samples/aws-mainframe-modernization-carddemo.git"
    workspace_dir = os.path.join("workspaces", "carddemo")

    # Clone it if we don't have it
    if not os.path.exists(workspace_dir):
        print(f"📥 Cloning repository into {workspace_dir}...")
        subprocess.run(["git", "clone", repo_url, workspace_dir], check=True)
    else:
        print(f"📂 Found existing repository at {workspace_dir}. Using cached version.")
    
    # Scan the ENTIRE repository for COBOL files instead of guessing folder names!
    search_pattern = os.path.join(workspace_dir, "**", "*.[cC][bB][lL]")
    cobol_files = glob.glob(search_pattern, recursive=True)
    
    print(f"\n📊 INVENTORY MANIFEST: Found {len(cobol_files)} COBOL programs.")
    
    # 2. Run the Engine (Worker 3)
    json_artifacts = []
    for file_path in cobol_files:
        print(f"\n⚙️ Parsing: {os.path.basename(file_path)}")
        try:
            # The exact pipeline you built!
            resolved_path = parser.resolve_copybooks(file_path, workspace_dir)
            dialect = parser.fingerprint_dialect(resolved_path)
            clean_path = parser.normalize_dialect(resolved_path, dialect)
            ast_path = parser.generate_ast_json(clean_path)
            
            if ast_path:
                json_artifacts.append(ast_path)
        except Exception as e:
            print(f"💥 Parse failed for {os.path.basename(file_path)}: {e}")

    # 3. Run the Cartographer (Worker 4)
    if json_artifacts:
        cartographer.generate_service_decomposition(json_artifacts, workspace_dir)
    else:
        print("❌ No valid JSONs generated. Cartographer cannot run.")

if __name__ == "__main__":
    run_real_world_analysis()