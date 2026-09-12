import os
import json
from datetime import datetime
def generate_documentation(skill_name, description, parameters, example_usage):
    doc = {
        "skill_name": skill_name,
        "description": description,
        "parameters": parameters,
        "example_usage": example_usage,
        "created_at": datetime.now().isoformat()
    }
    file_name = f"{skill_name}_documentation.json"
    with open(file_name, 'w') as f:
        json.dump(doc, f, indent=4)
def run(params):
    skill_name = params.get("skill_name")
    description = params.get("description")
    parameters = params.get("parameters", {})
    example_usage = params.get("example_usage", "")
    generate_documentation(skill_name, description, parameters, example_usage)
    return {"status": "Documentation generated", "file": f"{skill_name}_documentation.json"}