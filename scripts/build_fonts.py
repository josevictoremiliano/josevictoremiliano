"""Gera os subconjuntos de fonte (WOFF2) que vão embutidos nos cards SVG.

Rode só quando quiser trocar fonte ou adicionar caracteres:
    python scripts/build_fonts.py <pasta-com-os-ttf-originais>

Originais (Google Fonts, licença OFL):
    Baloo2[wght].ttf, BaiJamjuree-Regular.ttf, BaiJamjuree-Medium.ttf,
    ShadowsIntoLight.ttf, JetBrainsMono[wght].ttf
"""
import sys
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "fonts"

# ASCII imprimível + acentos do português + alguns símbolos usados nos cards
CHARS = "".join(chr(c) for c in range(0x20, 0x7F)) + "áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ·—–→↗↘★•…“”‘’"

# (arquivo de origem, peso p/ instanciar fonte variável, nome de saída)
FONTS = [
    ("Baloo2.ttf", 800, "baloo2-800"),
    ("BaiReg.ttf", None, "bai-400"),
    ("BaiMed.ttf", None, "bai-500"),
    ("Hand.ttf", None, "hand-400"),
    ("Mono.ttf", 500, "mono-500"),
]


def main(src_dir: Path) -> None:
    OUT.mkdir(exist_ok=True)
    for src, weight, name in FONTS:
        font = TTFont(src_dir / src)
        if weight is not None and "fvar" in font:
            font = instantiateVariableFont(font, {"wght": weight})
        opts = Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "liga"]
        opts.name_IDs = []
        sub = Subsetter(opts)
        sub.populate(text=CHARS)
        sub.subset(font)
        font.flavor = "woff2"
        dest = OUT / f"{name}.woff2"
        font.save(dest)
        print(f"{dest.name}: {dest.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
