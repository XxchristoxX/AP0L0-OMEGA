import requests
import json
def check_password_breach(password):
    url = f"https://api.pwnedpasswords.com/range/{password[:5]}"
    response = requests.get(url)
    
    if response.status_code != 200:
        raise RuntimeError(f"Error fetching: {response.status_code}")

    hashes = (line.split(':') for line in response.text.splitlines())
    return {hash: int(count) for hash, count in hashes}
def run(params):
    password = params.get('password')
    if not password:
        return {"error": "No password provided"}
    
    try:
        breach_data = check_password_breach(password)
        if password[5:] in breach_data:
            return {"breached": True, "count": breach_data[password[5:]]}
        else:
            return {"breached": False}
    except Exception as e:
        return {"error": str(e)}