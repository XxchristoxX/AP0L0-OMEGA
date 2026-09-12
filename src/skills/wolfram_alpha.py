import requests
import json
def run(params):
    app_id = params.get('app_id')
    query = params.get('query')
    if not app_id or not query:
        return "Error: app_id and query are required"
    url = f"http://api.wolframalpha.com/v2/query?input={query}&format=plaintext&output=JSON&appid={app_id}"
    response = requests.get(url)
    if response.status_code != 200:
        return "Error: Unable to reach Wolfram Alpha API"
    data = response.json()
    if 'queryresult' in data and data['queryresult']['success']:
        pods = data['queryresult']['pods']
        result = []
        for pod in pods:
            if 'subpods' in pod:
                for subpod in pod['subpods']:
                    result.append(subpod['plaintext'])
        return result
    else:
        return "Error: No results found"
    # print(run(params))