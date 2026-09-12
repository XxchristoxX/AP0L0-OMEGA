from .catalog import SkillsCatalog
class BuiltInAgents:
    def __init__(self): self.catalog = SkillsCatalog()
    def morning_digest(self): return "Morning digest."
    def deep_research(self, t=""): return f"Deep research: {t}"
    def code_assistant(self, t=""): return f"Code: {t}"
