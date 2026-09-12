def g0dm0d3_jailbreak(data):
    if not isinstance(data, dict):
        return "Error: Input must be a dictionary."
    result = {}
    for key, value in data.items():
        if isinstance(value, int):
            result[key] = value * 2
        elif isinstance(value, str):
            result[key] = value[::-1]
        else:
            result[key] = "Unsupported type"
    return result
def run(data):
    return g0dm0d3_jailbreak(data)