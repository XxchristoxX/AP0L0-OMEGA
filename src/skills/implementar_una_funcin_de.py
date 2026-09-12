import os
import json
import datetime
def backup_skills(backup_directory, skills):
    if not os.path.exists(backup_directory):
        os.makedirs(backup_directory)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_directory, f"skills_backup_{timestamp}.json")
    
    with open(backup_file, 'w') as f:
        json.dump(skills, f)
    
    return backup_file
def restore_skills(backup_file):
    with open(backup_file, 'r') as f:
        skills = json.load(f)
    return skills
def run(params):
    action = params.get("action")
    skills = params.get("skills", {})
    backup_directory = params.get("backup_directory", "./backups")
    
    if action == "backup":
        result = backup_skills(backup_directory, skills)
        return {"status": "success", "backup_file": result}
    elif action == "restore":
        backup_file = params.get("backup_file")
        if not backup_file or not os.path.exists(backup_file):
            return {"status": "error", "message": "Backup file does not exist."}
        restored_skills = restore_skills(backup_file)
        return {"status": "success", "restored_skills": restored_skills}
    else:
        return {"status": "error", "message": "Invalid action."}