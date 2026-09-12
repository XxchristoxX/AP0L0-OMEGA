import json
from flask import Flask, request, jsonify
def manage_skills():
    if request.method == 'POST':
        skill = request.json
        skills[skill['name']] = skill
        return jsonify(skill), 201
    return jsonify(skills)
def run(params):
    if 'action' in params:
        if params['action'] == 'add':
            skills[params['name']] = params
            return {"status": "success", "skill": params}
        elif params['action'] == 'get':
            return skills.get(params['name'], {"status": "not found"})
    return {"status": "invalid action"}
if __name__ == "__main__":
    if __name__ == '__main__':
        app.run(debug=True)