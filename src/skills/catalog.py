CATALOG = {"morning_digest":"Morning summary","deep_research":"Deep research","code_assistant":"Code assistant"}
class SkillsCatalog:
    def list_skills(self): return list(CATALOG.keys())
    def get_description(self, name): return CATALOG.get(name,"")
