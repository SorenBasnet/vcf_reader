import json
import time
from pathlib import Path

def create_gwas_repository(repo_dir: str, title: str, description: str, author: str, gwas_file: str, trait: str, sample_size: int) -> dict:

    path = Path(repo_dir)
    path.mkdir(parents=True, exist_ok=True) 

    manifest = {
            "repository_name": path.name, 
            "title": title, 
            "description": description, 
            "author": author, 
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "phenotype": {
                "trait": trait, 
                "sample_size": sample_size
                },
            "files":{
                "gwas_results": gwas_file, 
                "manifest": "cintern_repo.json"
                }, 
            "visibility": "private"
            }

    manifest_path = path / "cintern_repo.json"

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent = 4)


    return manifest


