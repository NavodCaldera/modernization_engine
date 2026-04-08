import os
import json
import subprocess
import re  # <-- Needed for dialect normalization
from openai import OpenAI
from dotenv import load_dotenv

# Load the secret API key from the .env file
load_dotenv()

# --- 1. RECURSIVE COPYBOOK RESOLVER (v3.0 Upgrade) ---
def resolve_copybooks(file_path, workspace_dir, visited_copybooks=None):
    if visited_copybooks is None:
        visited_copybooks = set()

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    
    # CYCLE DETECTION: Stop infinite loops if a copybook calls itself!
    if base_name.upper() in visited_copybooks:
        print(f"  -> 🔄 Cycle detected! Skipping already inlined copybook: {base_name}")
        return file_path
        
    visited_copybooks.add(base_name.upper())
    print(f"\nStarting Copybook Resolver for: {os.path.basename(file_path)}...")
    
    resolved_file_path = os.path.splitext(file_path)[0] + "_resolved.cbl"
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        
    resolved_lines = []
    for line in lines:
        clean_line = line.strip().upper()
        if clean_line.startswith("COPY "):
            parts = clean_line.split("COPY ")
            copybook_name = parts[1].replace("'", "").replace('"', "").replace(".", "").strip()
            
            found = False
            for root, dirs, files in os.walk(workspace_dir):
                for file in files:
                    if file.upper() == f"{copybook_name}.CPY" or file.upper() == copybook_name:
                        copybook_path = os.path.join(root, file)
                        try:
                            # RECURSIVE CALL: Resolve the copybook before we inline it!
                            resolved_cb_path = resolve_copybooks(copybook_path, workspace_dir, visited_copybooks)
                            
                            with open(resolved_cb_path, 'r', encoding='utf-8', errors='ignore') as cb_file:
                                resolved_lines.append(f"      * --- START INLINED COPY: {copybook_name} ---\n")
                                resolved_lines.extend(cb_file.readlines())
                                resolved_lines.append(f"\n      * --- END INLINED COPY: {copybook_name} ---\n")
                                found = True
                                print(f"  -> 📥 Successfully inlined copybook: {copybook_name}")
                                break
                        except Exception as e:
                            print(f"  -> ⚠️ Error reading copybook {copybook_path}: {e}")
                if found: break
            
            if not found:
                resolved_lines.append(f"      * ERROR: COPYBOOK {copybook_name} NOT FOUND\n")
        else:
            resolved_lines.append(line)
            
    with open(resolved_file_path, 'w', encoding='utf-8') as f:
        f.writelines(resolved_lines)
    return resolved_file_path

# --- 2. DIALECT FINGERPRINTER (v3.0 Upgrade) ---
def fingerprint_dialect(file_path):
    print(f"Inspecting COBOL file: {os.path.basename(file_path)} for dialect fingerprints...")
    dialect = "ANSI-85" # Default
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for i, line in enumerate(f):
            if i > 50: break # Only check the top 50 lines for headers
            clean_line = line.strip().upper()
            
            # Look for IBM Mainframe markers
            if "CBL " in clean_line or "PROCESS " in clean_line:
                dialect = "IBM-Enterprise"
                break
            # Look for MicroFocus markers
            elif "$SET " in clean_line:
                dialect = "MicroFocus"
                break
                
    print(f"  -> Dialect Detected: {dialect}")
    return dialect

# --- 3. DIALECT PREPROCESSOR (v3.0 Upgrade) ---
def normalize_dialect(file_path, dialect):
    base_name = os.path.splitext(file_path)[0]
    normalized_file_path = base_name + "_normalized.cbl"
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        code = f.read()
        
    # Translate vendor-specific syntax to standard ANSI-85 so ProLeap doesn't crash
    if dialect == "IBM-Enterprise":
        # Change IBM's proprietary COMP-5 (native binary) to standard COMP
        code = re.sub(r'COMP-5', 'COMP', code, flags=re.IGNORECASE)
        code = re.sub(r'COMP-4', 'COMP', code, flags=re.IGNORECASE)
    elif dialect == "MicroFocus":
        # Change MicroFocus proprietary COMP-X to standard COMP
        code = re.sub(r'COMP-X', 'COMP', code, flags=re.IGNORECASE)
        
    with open(normalized_file_path, 'w', encoding='utf-8') as clean_file:
        clean_file.write(code)
        
    return normalized_file_path

# --- TIER 2: CUSTOM ANTLR4 GRAMMAR FALLBACK ---
def custom_antlr4_parse(file_path):
    print(f"⚠️ PROLEAP FAILED. Attempting Tier 2: Custom ANTLR4 Grammar for {os.path.basename(file_path)}...")
    # Architecture Placeholder: This is where you would call a custom compiled ANTLR4 Python target.
    # Because writing a custom grammar takes months, we will simulate a failure here to route to the LLM.
    raise ValueError("Custom ANTLR4 Grammar could not resolve vendor-specific extensions.")

# --- TIER 3: OPENAI LLM FALLBACK ---
def llm_fallback_parse(file_path, original_dialect):
    print(f"⚠️ ANTLR4 FAILED. Triggering Tier 3: OpenAI LLM Fallback Parse...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        raw_code = f.read()
        
    client = OpenAI() # Automatically pulls from your .env file
    
    # Updated LLM Schema to match the new Data Models and APIs logic
    prompt = f"""
    You are an expert COBOL legacy modernization architect.
    The following COBOL code failed strict ANSI-85 parsing, likely due to IBM/DB2 vendor extensions.
    
    Extract the architecture data and return it STRICTLY as a JSON object with this exact schema:
    {{
        "is_parsed_by_proleap": false,
        "is_parsed_by_llm": true,
        "file_name": "{os.path.basename(file_path)}",
        "status": "RECOVERED_BY_AI",
        "dependencies": ["LIST", "OF", "CALL", "TARGETS"],
        "exec_blocks": ["LIST OF RAW EXEC SQL STRINGS"],
        "file_descriptors": ["LIST OF VSAM DATASET NAMES"],
        "api_contracts": [
            {{"variable_name": "NAME", "level": "01", "pic": "9(5)", "usage": "COMP-3"}}
        ],
        "data_models": {{
            "DATASET_NAME": [
                {{"variable_name": "NAME", "level": "01", "pic": "9(5)", "usage": "COMP-3"}}
            ]
        }},
        "symbol_table": [
            {{"variable_name": "NAME", "level": "01", "pic": "9(5)", "usage": "COMP-3"}}
        ]
    }}
    
    COBOL CODE TO ANALYZE:
    {raw_code[:8000]} # Truncating to 8000 chars to save tokens during testing
    """

    print("🤖 (OpenAI GPT-4o is reading the COBOL code...)")
    
    try:
        # V3.0 Spec: Deterministic outputs! Temp = 0, JSON mode enforced.
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": "You are a precise COBOL AST extraction engine. Output only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            seed=42
        )
        
        llm_ast = json.loads(response.choices[0].message.content)
        
        # V3.0 Spec: Inject DialectAnnotation metadata for Cartographer / Worker 8
        llm_ast["dialect_annotation"] = {
            "source_dialect": original_dialect,
            "parse_method": "LLM_GPT4o",
            "confidence": "low" # Forces mandatory I/O parity testing later!
        }
        
        base_name = os.path.splitext(file_path)[0]
        ast_file_path = base_name + "_ast.json"
        
        with open(ast_file_path, 'w', encoding='utf-8') as json_file:
            json.dump(llm_ast, json_file, indent=4)
            
        return ast_file_path
        
    except Exception as e:
        print(f"💥 FATAL LLM ERROR: Could not recover {file_path}. Error: {e}")
        return None

# --- TIER 1: THE PRIMARY ENGINE ---
def generate_ast_json(clean_file_path, dialect="ANSI-85"):
    print(f"\nStarting the ProLeap Parser Engine for: {os.path.basename(clean_file_path)}...")
    
    jar_path = os.path.join("parser_engine", "proleap-bridge", "target", "proleap-bridge-1.0-SNAPSHOT-jar-with-dependencies.jar")
    
    if not os.path.exists(jar_path):
        print(f"❌ Error: Could not find the ProLeap bridge at {jar_path}")
        return None

    try:
        # TIER 1: RUN JAVA PROLEAP ENGINE
        result = subprocess.run(
            ["java", "-jar", jar_path, clean_file_path],
            capture_output=True, text=True, check=True
        )
        
        ast_data = json.loads(result.stdout.strip())
        if "error" in ast_data:
            raise ValueError(ast_data["error"])
        
        print("🔍 Extracting Symbols, Data Models, APIs, and EXEC Blocks...")
        
        symbols, dependencies, exec_blocks, file_descriptors = [], [], [], []
        data_models = {}  # To store the variables inside the VSAM files
        api_contracts = [] # To store the variables in the LINKAGE SECTION
        
        in_exec = False
        in_linkage = False
        current_fd = None
        current_exec = []
        
        with open(clean_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                clean_line = line.strip().upper()
                
                # --- NEW: SECTION TRACKING FOR APIs AND DATA MODELS ---
                if "LINKAGE SECTION" in clean_line:
                    in_linkage = True
                    current_fd = None
                elif "PROCEDURE DIVISION" in clean_line or "WORKING-STORAGE SECTION" in clean_line:
                    in_linkage = False
                    current_fd = None
                
                if clean_line.startswith("FD "):
                    parts = clean_line.split()
                    if len(parts) > 1:
                        current_fd = parts[1].replace(".", "")
                        if current_fd not in file_descriptors:
                            file_descriptors.append(current_fd)
                        data_models[current_fd] = [] # Initialize the table
                        in_linkage = False
                
                # Extract Variables
                elif clean_line.startswith(("01 ", "05 ", "10 ", "77 ")):
                    parts = [p.replace(".", "") for p in clean_line.split()]
                    if len(parts) > 1:
                        var_name = parts[1]
                        pic_clause = parts[parts.index("PIC") + 1] if "PIC" in parts and parts.index("PIC") + 1 < len(parts) else ""
                        usage_clause = "COMP-3" if "COMP-3" in parts else ("COMP" if "COMP" in parts else "DISPLAY")
                        
                        var_data = {"variable_name": var_name, "level": parts[0], "pic": pic_clause, "usage": usage_clause}
                        symbols.append(var_data)
                        
                        # Route the variable to the correct architecture bucket!
                        if in_linkage:
                            api_contracts.append(var_data)
                        elif current_fd:
                            data_models[current_fd].append(var_data)
                
                # Extract CALL dependencies
                elif "CALL " in clean_line:
                    parts = clean_line.split("CALL ")
                    if len(parts) > 1:
                        target = parts[1].replace("'", "").replace('"', "").replace(".", "").split()[0]
                        if target not in dependencies: dependencies.append(target)
                            
                # Extract EXEC SQL / EXEC CICS blocks
                if "EXEC SQL" in clean_line or "EXEC CICS" in clean_line:
                    in_exec = True
                    current_exec = [clean_line]
                elif in_exec:
                    current_exec.append(clean_line)
                    if "END-EXEC" in clean_line:
                        in_exec = False
                        exec_blocks.append(" ".join(current_exec))

        ast_data["symbol_table"] = symbols
        ast_data["dependencies"] = dependencies
        ast_data["exec_blocks"] = exec_blocks
        ast_data["file_descriptors"] = file_descriptors
        ast_data["data_models"] = data_models      # <-- SAVED!
        ast_data["api_contracts"] = api_contracts  # <-- SAVED!
        
        # V3.0 Spec: Inject successful DialectAnnotation metadata
        ast_data["dialect_annotation"] = {
            "source_dialect": dialect,
            "parse_method": "ProLeap_Strict",
            "confidence": "high"
        }
        
        base_name = os.path.splitext(clean_file_path)[0]
        ast_file_path = base_name + "_ast.json"
        
        with open(ast_file_path, 'w', encoding='utf-8') as json_file:
            json.dump(ast_data, json_file, indent=4)
            
        print(f"✅ AST with Data Models & APIs saved to: {ast_file_path}")
        return ast_file_path

    # THE 3-TIER ROUTING LOGIC
    except (subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as e:
        print(f"❌ Strict Parsing failed: {e}")
        try:
            # Fallback Tier 2
            return custom_antlr4_parse(clean_file_path)
        except ValueError:
            # Fallback Tier 3
            return llm_fallback_parse(clean_file_path, dialect)