import json
from typing import List, Dict

# `files` viene de st.file_uploader (objetos UploadedFile)
def load_json_files(files) -> List[Dict]:
    records = []
    for f in files:
        try:
            data = json.load(f)
            if isinstance(data, list):
                records.extend(data)
            elif isinstance(data, dict):
                if "hunts" in data and isinstance(data["hunts"], list):
                    records.extend(data["hunts"])
                else:
                    records.append(data)
        except Exception:
            f.seek(0)
            for line in f:
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue
    return records