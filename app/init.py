"""Interactive setup wizard for TailoredResume."""

import os
import shutil
from pathlib import Path

def run_init():
    print("=" * 60)
    print("Welcome to the TailoredResume Setup Wizard!")
    print("=" * 60)
    
    # Check .env
    env_file = Path(".env")
    if not env_file.exists():
        print("\n[1] Creating .env file...")
        if Path(".env.example").exists():
            shutil.copy(".env.example", ".env")
        else:
            env_file.write_text("GEMINI_API_KEY=\nGEMINI_MODEL=gemini-3-flash-preview\n")
            
        api_key = input("Enter your Gemini API Key (or press Enter to skip): ").strip()
        if api_key:
            content = env_file.read_text()
            content = content.replace("GEMINI_API_KEY=", f"GEMINI_API_KEY={api_key}")
            env_file.write_text(content)
        print("Created .env")
    else:
        print("\n[1] .env file already exists. Skipping.")
        
    # Ask for base resume
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    base_resume = data_dir / "base_resume.md"
    
    if not base_resume.exists():
        print("\n[2] Setting up Base Resume...")
        print("Please enter the absolute path to your base resume (markdown or text file),")
        resume_path = input("or press Enter to create an empty template: ").strip()
        
        if resume_path and Path(resume_path).exists():
            shutil.copy(resume_path, base_resume)
            print(f"Copied {resume_path} to {base_resume}")
        else:
            base_resume.write_text("# John Doe\n\n## Experience\n\n* Software Engineer...", encoding="utf-8")
            print(f"Created a template base resume at {base_resume}")
    else:
        print("\n[2] Base resume already exists. Skipping.")
        
    print("\nSetup Complete!")
    print("You can now run `python main.py run` to start the autonomous pipeline.")
