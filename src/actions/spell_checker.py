# src/actions/spell_checker.py
# Corrección ortográfica simple (si está instalado pyspellchecker)
try:
    from spellchecker import SpellChecker
    _SPELL_AVAILABLE = True
except ImportError:
    _SPELL_AVAILABLE = False

class SpellCheckerService:
    def __init__(self):
        if _SPELL_AVAILABLE:
            self.spell = SpellChecker(language='es')
        else:
            self.spell = None
            print("[SpellChecker] pyspellchecker no instalado. Ejecuta: pip install pyspellchecker")

    def correct_text(self, text: str) -> str:
        if not self.spell:
            return "Corrector ortográfico no disponible."
        words = text.split()
        corrected = []
        for w in words:
            w_clean = w.strip('.,!?')
            if w_clean and not self.spell.unknown([w_clean]):
                corrected.append(w)
            else:
                corrected.append(self.spell.correction(w_clean) or w)
        return " ".join(corrected)