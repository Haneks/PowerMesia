"""
Génère output/demo_refrain.pptx : un chant structuré (paroles inventées) dont le refrain
est en gras et répété après chaque couplet. À ouvrir dans PowerPoint pour contrôle visuel.

    python scripts/demo_refrain_pptx.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from context.models import SectionChant, TypeSection
from tools.chant_structure import compute_ordre, sections_to_dicts
from tools.pptx_generator import generate_pptx

SECTIONS = [
    SectionChant("R", TypeSection.REFRAIN, ["Chantons au Seigneur un chant nouveau,", "Alléluia, alléluia !"]),
    SectionChant("1", TypeSection.COUPLET, ["Le matin se lève sur la ville,", "Les cloches annoncent le jour."]),
    SectionChant("2", TypeSection.COUPLET, ["Le soir descend sur la vallée,", "Nous rendons grâce pour ce jour."]),
]


def main() -> Path:
    out = ROOT / "output" / "demo_refrain.pptx"
    bloc = {
        "type": "chant",
        "titre": "Chant de démonstration",
        "paroles": "",
        "structure": sections_to_dicts(SECTIONS),
        "ordre_chant": compute_ordre(SECTIONS),
    }
    generate_pptx([bloc], out)
    return out


if __name__ == "__main__":
    print(f"Fichier généré : {main()}")
