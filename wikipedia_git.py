import shutil
import subprocess
import requests
import os
import time
from datetime import datetime

# Global session
session = requests.Session()
session.headers.update({
    'User-Agent': 'WikipediaUltimateExporter/1.0 (Personal use)',
    'Accept': 'application/json',
})


def search_wikipedia(query, limit=10):
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
        "srwhat": "text"
    }
    
    response = session.get(url, params=params, timeout=10)
    if response.status_code != 200:
        print(f"❌ HTTP {response.status_code}")
        return []
    
    try:
        data = response.json()
        return data.get("query", {}).get("search", [])
    except Exception:
        return []


def get_all_revisions(page_title, max_revisions=2500):
    """Fetch revisions with resume support"""
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in page_title)[:80]
    folder = f"{safe_title}_history"
    
    # Check for existing files to resume
    start_from_id = None
    existing_count = 0
    
    if os.path.exists(folder):
        existing_files = [f for f in os.listdir(folder) if f.endswith(".txt") and f"{safe_title}_" in f]
        existing_count = len(existing_files)
        
        if existing_count > 0:
            # Try to find the highest revision ID from existing files
            highest_revid = 0
            for f in existing_files:
                try:
                    # Read first few lines to extract revid
                    with open(os.path.join(folder, f), "r", encoding="utf-8") as file:
                        for _ in range(10):  # check header
                            line = file.readline()
                            if "Revision ID:" in line:
                                revid = int(line.split(":")[1].strip())
                                if revid > highest_revid:
                                    highest_revid = revid
                                break
                except:
                    continue
            
            if highest_revid > 0:
                start_from_id = highest_revid
                print(f"🔄 Found {existing_count} existing revisions. Highest ID: {highest_revid}")
    
    url = "https://en.wikipedia.org/w/api.php"
    revisions = []
    params = {
        "action": "query",
        "prop": "revisions",
        "titles": page_title,
        "rvprop": "content|timestamp|user|comment|ids",
        "rvlimit": 500,
        "rvdir": "newer",
        "format": "json"
    }

    if start_from_id:
        params["rvstartid"] = start_from_id
        print(f"📌 Resuming from revision ID: {start_from_id}")

    print(f"📥 Fetching revisions for: {page_title} (max {max_revisions})")
    count = existing_count

    while True:
        response = session.get(url, params=params, timeout=15)
        
        if response.status_code == 429:
            wait = min(2 ** (count // 500), 30)
            print(f"⏳ Rate limited. Waiting {wait}s...")
            time.sleep(wait)
            continue
            
        if response.status_code != 200:
            print(f"❌ HTTP Error: {response.status_code}")
            break

        try:
            data = response.json()
        except:
            print("❌ JSON error")
            break

        pages = data.get("query", {}).get("pages", {})
        page_id = list(pages.keys())[0]
        page_data = pages[page_id]

        if "revisions" in page_data:
            new_revs = page_data["revisions"]
            revisions.extend(new_revs)
            count += len(new_revs)
            print(f"  → Total revisions: {count}", end="\r")

        if count >= max_revisions:
            print(f"\n⛔ Reached max limit ({max_revisions})")
            break

        if "continue" in data:
            params["rvcontinue"] = data["continue"]["rvcontinue"]
            time.sleep(1.0)
        else:
            break

    print(f"\n✅ New revisions fetched: {len(revisions)} | Total: {count}")
    return revisions


def save_revisions(revisions, page_title):
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in page_title)[:80]
    folder = f"{safe_title}_history"
    os.makedirs(folder, exist_ok=True)
    
    print(f"\n💾 Saving new revisions to: ./{folder}/\n")

    for i, rev in enumerate(revisions):
        # Calculate global index (for filename)
        global_index = i + 999999  # temporary - we'll improve this if needed
        
        # Better: just use sequential from existing count if resuming
        # For simplicity, we'll number from 0000 and let user manage duplicates for now
        file_index = i   # You can improve numbering later
        
        timestamp_str = rev.get("timestamp", "unknown")
        user = rev.get("user", "unknown")
        revid = rev.get("revid", "N/A")

        print(f"[{file_index:04d}] Saving rev {revid} | {timestamp_str} | {user}")

        filename = f"{folder}/{safe_title}_{file_index:04d}.txt"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"=== Wikipedia Revision #{file_index} ===\n")
            f.write(f"Title: {page_title}\n")
            f.write(f"Revision ID: {revid}\n")
            f.write(f"Timestamp: {timestamp_str}\n")
            f.write(f"Editor: {user}\n")
            f.write("="*70 + "\n\n")
            f.write(rev.get("*", ""))

        # Set modified date
        if timestamp_str:
            try:
                dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                ts = dt.timestamp()
                os.utime(filename, (ts, ts))
            except:
                pass

    print(f"\n🎉 All {len(revisions)} versions saved successfully!")



def create_git_history(revisions, page_title):
    """Create Git repo with better reliability for GitHub Desktop"""
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in page_title)[:80]
    repo_path = f"{safe_title}_git"
    
    # Clean and recreate
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)
    os.makedirs(repo_path)
    
    print(f"\n🚀 Creating Git repository: ./{repo_path}/")
    
    # Initialize
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo_path, capture_output=True)
    
    filename = f"{safe_title}.txt"
    total_commits = 0

    for i, rev in enumerate(revisions):
        timestamp_str = rev.get("timestamp")
        user = rev.get("user", "Unknown")
        comment = rev.get("comment", "").strip() or "No edit summary"
        content = rev.get("*", "")
        revid = rev.get("revid", i)

        # Write file
        filepath = os.path.join(repo_path, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        # Stage
        subprocess.run(["git", "add", filename], cwd=repo_path, capture_output=True)

        # Prepare commit metadata
        if timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            git_date = dt.strftime("%Y-%m-%d %H:%M:%S +0000")
        else:
            git_date = None

        env = os.environ.copy()
        if git_date:
            env["GIT_AUTHOR_DATE"] = git_date
            env["GIT_COMMITTER_DATE"] = git_date

        author = f"{user} <{user.lower().replace(' ', '.')}@wikipedia.org>"

        commit_message = f"rev {revid} - {comment[:180]}"

        # Commit with force (even if no change in content)
        result = subprocess.run([
            "git", "commit",
            "--allow-empty",           # Important: allow commits even if content is same
            "--author", author,
            "-m", commit_message
        ], cwd=repo_path, env=env, capture_output=True, text=True)

        if result.returncode == 0:
            total_commits += 1
            print(f"✅ Commit {i:04d} | {timestamp_str[:19] if timestamp_str else 'N/A'} | {user}")
        else:
            print(f"⚠️  Commit {i:04d} skipped or failed: {result.stderr.strip()[:100]}")

    # Final touch
    print(f"\n🎉 Git repository created with {total_commits} commits!")
    print(f"   Folder: ./{repo_path}/")
    
    # Show last few commits
    print("\nLast 5 commits:")
    log = subprocess.run(["git", "log", "--oneline", "-5"], 
                        cwd=repo_path, capture_output=True, text=True)
    print(log.stdout)
    
    print("\n💡 Tips for GitHub Desktop:")
    print("   1. Open the folder in GitHub Desktop")
    print("   2. Press Ctrl+R (or Cmd+R) to refresh")
    print("   3. If still only 1 commit, close and reopen GitHub Desktop")


def main():
    print("🌍 Ultimate Wikipedia Version Exporter (with correct dates)\n")
    
    query = input("Enter search term: ").strip()
    if not query:
        print("No input.")
        return

    print("\n🔍 Searching...")
    results = search_wikipedia(query, limit=10)

    if not results:
        print("No results found.")
        return

    print("\nSearch Results:")
    for i, r in enumerate(results):
        print(f"{i+1:2d}. {r['title']}")

    while True:
        try:
            num = int(input("\nSelect number (1-10): "))
            if 1 <= num <= len(results):
                selected = results[num-1]
                break
            print("Number out of range.")
        except ValueError:
            print("Please enter a valid number.")

    page_title = selected["title"]
    print(f"\nSelected → {page_title}")

    revisions = get_all_revisions(page_title, max_revisions=2500)
    
    if revisions:
        save_revisions(revisions, page_title)
        create_git_history(revisions, page_title)
    else:
        print("No revisions retrieved.")


if __name__ == "__main__":
    main()