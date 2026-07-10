import filecmp
import shutil
import subprocess
from pathlib import Path

def test_golden_scaffolding(tmp_path: Path):
    """
    Generate a projection into a temp directory and compare it with the golden snapshot.
    If the golden snapshot does not exist, it creates it.
    This prevents unintended drift in the generated templates.
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    golden_dir = project_root / "tests" / "fixtures" / "golden_projection"
    
    out_dir = tmp_path / "golden_proj"
    
    # Generate the projection using the CLI
    cmd = [
        "python", "-m", "rationalevault.cli.main", 
        "new", "projection", "golden_proj",
        "--with-cli", "--with-mcp"
    ]
    subprocess.run(cmd, cwd=tmp_path, check=True)
    
    if not golden_dir.exists():
        # First time setup, just copy
        shutil.copytree(out_dir, golden_dir)
        return
        
    # Compare trees
    match, mismatch, errors = compare_directories(out_dir, golden_dir)
    
    assert not errors, f"Errors comparing directories: {errors}"
    assert not mismatch, f"Mismatch found in generated scaffolding: {mismatch}"

def compare_directories(dir1: Path, dir2: Path):
    cmp = filecmp.dircmp(dir1, dir2)
    match, mismatch, errors = [], [], []
    
    mismatch.extend([f"{dir1.name}/{f}" for f in cmp.left_only])
    mismatch.extend([f"{dir2.name}/{f}" for f in cmp.right_only])
    mismatch.extend([f"Diff: {f}" for f in cmp.diff_files])
    
    for common_dir in cmp.common_dirs:
        m, mm, e = compare_directories(dir1 / common_dir, dir2 / common_dir)
        match.extend(m)
        mismatch.extend(mm)
        errors.extend(e)
        
    return match, mismatch, errors
