import os
import re

def refactor_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # We will find function definitions, check if user_id is in params,
    # and if so, replace `with get_connection() as conn:` with `with get_connection(user_id) as conn:`
    # inside that function's body.
    
    # We can just use a simple regex that looks for `def function_name(...user_id...):`
    # and replaces `with get_connection() as conn:` until the next `def ` or end of file.
    
    lines = content.split('\n')
    has_user_id = False
    
    for i in range(len(lines)):
        line = lines[i]
        
        # Detect function defs
        if line.startswith("def "):
            if "user_id" in line:
                has_user_id = True
            else:
                has_user_id = False
                
        if has_user_id and "with get_connection() as conn:" in line:
            lines[i] = line.replace("with get_connection() as conn:", "with get_connection(user_id) as conn:")
            
    with open(filepath, "w", encoding="utf-8") as f:
        f.write('\n'.join(lines))

if __name__ == "__main__":
    refactor_file("app/db.py")
    refactor_file("app/resumes.py")
    refactor_file("app/search_config.py")
    print("Refactored successfully.")
