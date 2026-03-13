"""Fix migration chain by analyzing all migration files"""
import re
from pathlib import Path

def extract_revision_info(file_path):
    """Extract revision, down_revision from migration file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    revision_match = re.search(r"^revision = ['\"](.+?)['\"]", content, re.MULTILINE)
    down_revision_match = re.search(r"^down_revision = ['\"](.+?)['\"]", content, re.MULTILINE)
    
    revision = revision_match.group(1) if revision_match else None
    down_revision = down_revision_match.group(1) if down_revision_match else None
    
    return revision, down_revision

def main():
    """Analyze migration chain"""
    versions_dir = Path(__file__).parent.parent / "alembic" / "versions"
    
    migrations = []
    for file_path in versions_dir.glob("*.py"):
        if file_path.name.startswith("__"):
            continue
        
        revision, down_revision = extract_revision_info(file_path)
        if revision:
            migrations.append({
                'file': file_path.name,
                'revision': revision,
                'down_revision': down_revision
            })
    
    # Sort by filename
    migrations.sort(key=lambda x: x['file'])
    
    print("=" * 80)
    print("MIGRATION CHAIN ANALYSIS")
    print("=" * 80)
    
    for m in migrations:
        print(f"\nFile: {m['file']}")
        print(f"  Revision: {m['revision']}")
        print(f"  Down Revision: {m['down_revision']}")
    
    # Find issues
    print("\n" + "=" * 80)
    print("ISSUES FOUND")
    print("=" * 80)
    
    revisions = {m['revision'] for m in migrations}
    
    for m in migrations:
        if m['down_revision'] and m['down_revision'] not in revisions and m['down_revision'] != 'None':
            print(f"\n❌ {m['file']}")
            print(f"   References missing down_revision: {m['down_revision']}")
    
    # Check for duplicates
    revision_counts = {}
    for m in migrations:
        rev = m['revision']
        if rev in revision_counts:
            revision_counts[rev].append(m['file'])
        else:
            revision_counts[rev] = [m['file']]
    
    for rev, files in revision_counts.items():
        if len(files) > 1:
            print(f"\n❌ Duplicate revision '{rev}' in:")
            for f in files:
                print(f"   - {f}")

if __name__ == "__main__":
    main()
