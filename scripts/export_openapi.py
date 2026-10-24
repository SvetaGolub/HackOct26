import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from app.main import app

output = root / "openapi.json"
output.write_text(
    json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(f"Generated {output}")
