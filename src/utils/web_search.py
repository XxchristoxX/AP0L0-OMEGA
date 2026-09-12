from src.actions.web_search import web_search
def search_web(q, n=5):
    try: return str(web_search(parameters={"query":q,"mode":"search","items":n}, player=None))
    except: return "Search error"
