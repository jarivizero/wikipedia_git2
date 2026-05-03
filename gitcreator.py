import os
import glob
from datetime import datetime
import subprocess
import shutil

def list_history_folders():
    """List all *_history folders"""
    folders = [f for f in os.listdir('.') if os.path.isdir(f) and f.endswith('_history')]
    return sorted(folders)


def get_revision_files(folder):
    """Get all revision .txt files sorted by modified date (oldest first)"""
    files = glob.glob(os.path.join(folder, "*.txt"))
    
    file_list = []
    for f in files:
        mtime = os.path.getmtime(f)
        file_list.append((f, mtime))
    
    # Sort by modified time (oldest first)
    file_list.sort(key=lambda x: x[1])
    return file_list


def create_git_from_history(folder):
    """Convert _history folder into Git repo using file dates"""
    safe_name = folder.replace("_history", "")
    repo_path = f"{safe_name}_git"
    
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)
    os.makedirs(repo_path)
    
    print(f"🚀 Creating Git repo from: {folder}")
    print(f"   Output folder: {repo_path}\n")
    
    # Initialize git
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo_path, capture_output=True)
    
    revision_files = get_revision_files(folder)
    print(f"Found {len(revision_files)} revision files.\n")
    
    main_filename = f"{safe_name}.txt"
    
    for i, (filepath, mtime) in enumerate(revision_files):
        # Read content
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Extract revision info from header if possible
        rev_info = "Wikipedia Revision"
        try:
            first_lines = content.split('\n')[:10]
            for line in first_lines:
                if "Revision ID:" in line:
                    rev_info = line.strip()
                    break
        except:
            pass
        
        # Write to main file
        with open(os.path.join(repo_path, main_filename), "w", encoding="utf-8") as f:
            f.write(content)
        
        # Stage
        subprocess.run(["git", "add", main_filename], cwd=repo_path, capture_output=True)
        
        # Prepare commit date
        commit_date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S +0000")
        
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = commit_date
        env["GIT_COMMITTER_DATE"] = commit_date
        
        # Commit
        message = f"Revision {i:04d} - {rev_info}"
        
        result = subprocess.run([
            "git", "commit",
            "--allow-empty",
            "-m", message
        ], cwd=repo_path, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Commit {i:04d} | {datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')}")
        else:
            print(f"⚠️  Commit {i:04d} failed")
    
    print(f"\n🎉 Git repository successfully created!")
    print(f"   Path: ./{repo_path}/")
    print(f"   Commits: {len(revision_files)}")
    
    # Show summary
    print("\nLast 5 commits:")
    log = subprocess.run(["git", "log", "--oneline", "-5"], cwd=repo_path, capture_output=True, text=True)
    print(log.stdout or "No commits visible yet.")


def main():
    print("📂 Wikipedia History → Git Converter\n")
    
    folders = list_history_folders()
    
    if not folders:
        print("No *_history folders found in current directory.")
        return
    
    print("Available history folders:")
    for i, folder in enumerate(folders):
        print(f"{i+1:2d}. {folder}")
    
    while True:
        try:
            choice = int(input("\nSelect folder number: ")) - 1
            if 0 <= choice < len(folders):
                selected = folders[choice]
                break
            print("Invalid selection.")
        except ValueError:
            print("Please enter a number.")
    
    create_git_from_history(selected)


if __name__ == "__main__":
    main()