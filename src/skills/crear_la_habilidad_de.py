class Skill:
    def __init__(self, name):
        self.name = name
class LearningAI:
    def __init__(self):
        self.skills = []
    def learn_skill(self, skill_name):
        new_skill = Skill(skill_name)
        self.skills.append(new_skill)
    def show_skills(self):
        return [skill.name for skill in self.skills]
def run():
    ai = LearningAI()
    ai.learn_skill("Programación")
    ai.learn_skill("Matemáticas")
    return ai.show_skills()
if __name__ == "__main__":
    print(run())