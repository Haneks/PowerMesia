"""
Générateur PowerPoint - python-pptx.
Format 16:9, texte Calibri 54 noir centré, titre "[Titre] - x/y".
Le découpage du texte est dans tools/slicing.py.
"""

import html
import re
from pathlib import Path
from typing import Optional

import yaml
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_VERTICAL_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from tools.chant_structure import BlocLine, compute_ordre, expand_lines, sections_from_dicts
from tools.slicing import (
    DEFAULT_CHARS_PER_LINE,
    DEFAULT_MAX_CHARS,
    clean_spaces,
    split_lines_for_slides,
    split_text_for_slides,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "args" / "config.yaml"


def _load_config(config_path: Optional[Path] = None) -> dict:
    path = config_path or CONFIG_PATH
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return clean_spaces(text)


def _get_slide_dimensions(config: dict) -> tuple[float, float]:
    """Retourne (width, height) en inches selon aspect_ratio."""
    ratio = config.get("presentation", {}).get("aspect_ratio", "16:9")
    if ratio == "16:9":
        return 13.333, 7.5
    return 10.0, 7.5  # 4:3


def _rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color.lstrip("#").upper())


def _style_run(run, font_cfg: dict, default_size: int, bold: bool = False) -> None:
    run.font.name = font_cfg.get("font", "Calibri")
    run.font.size = Pt(font_cfg.get("size", default_size))
    run.font.color.rgb = _rgb(font_cfg.get("color", "#000000"))
    run.font.bold = bold


def _as_lines(text: str) -> list[BlocLine]:
    """Texte à plat → lignes (texte, gras=False)."""
    return [(line, False) for line in text.split("\n")]


def _write_lines(
    text_frame, lines: list[BlocLine], font_cfg: dict, default_size: int, bold: bool = False
) -> None:
    """
    Un paragraphe par ligne (les chants gardent leurs retours à la ligne).
    `bold` met tout en gras ; sinon le gras suit l'indicateur de chaque ligne (refrain).
    """
    for i, (line, line_bold) in enumerate(lines):
        p = text_frame.paragraphs[0] if i == 0 else text_frame.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        # Une ligne vide (entre deux couplets) garde la hauteur de la police.
        p.font.size = Pt(font_cfg.get("size", default_size))
        if line:
            _style_run(p.add_run(), font_cfg, default_size, bold or line_bold)
            p.runs[0].text = line


def _add_slide(
    prs: Presentation,
    config: dict,
    title: str,
    body: "str | list[BlocLine]",
    slide_type: str = "lecture",
) -> None:
    """Ajoute une slide centrée. slide_type: 'lecture' | 'chant' | 'message'."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    design = config.get("design", {})

    bg_cfg = design.get("background", {})
    bg_color = bg_cfg.get("color_chant" if slide_type == "chant" else "color", "#FFFFFF")
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = _rgb(bg_color)

    width_in, height_in = _get_slide_dimensions(config)
    margin = 0.4
    left = Inches(margin)
    width = Inches(width_in - 2 * margin)

    # Titre : "[Titre] - x/y"
    title_box = slide.shapes.add_textbox(left, Inches(0.3), width, Inches(0.6))
    title_box.text_frame.word_wrap = True
    _write_lines(
        title_box.text_frame, _as_lines(title), design.get("title", {}), 24,
        bold=design.get("title", {}).get("bold", True),
    )

    # Corps centré (horizontal et vertical)
    body_box = slide.shapes.add_textbox(left, Inches(1.0), width, Inches(height_in - 1.0 - 0.3))
    body_box.text_frame.word_wrap = True
    body_box.text_frame.vertical_anchor = MSO_VERTICAL_ANCHOR.MIDDLE
    body_lines = _as_lines(body) if isinstance(body, str) else body
    _write_lines(body_box.text_frame, body_lines, design.get("text", {}), 54)


def _chant_pages(bloc: dict, split_kwargs: dict) -> list:
    """
    Slides d'un chant. Chant structuré : ordre chanté, refrain en gras. Sinon : paroles à plat,
    comme avant.
    """
    sections = sections_from_dicts(bloc.get("structure") or [])
    if not sections:
        return split_text_for_slides(bloc.get("paroles", ""), mode="chant", **split_kwargs)
    ordre = bloc.get("ordre") or compute_ordre(sections)
    return split_lines_for_slides(expand_lines(sections, ordre), **split_kwargs)


def generate_pptx(
    blocs: list[dict],
    output_path: Path,
    config_path: Optional[Path] = None,
) -> Path:
    """Génère un fichier PowerPoint à partir d'une liste de blocs (lecture, chant, message)."""
    config = _load_config(config_path or CONFIG_PATH)
    slicing = config.get("slicing", {})
    split_kwargs = {
        "max_chars": slicing.get("max_chars_per_slide", DEFAULT_MAX_CHARS),
        "max_lines": slicing.get("max_lines_per_slide"),
        "chars_per_line": slicing.get("chars_per_line", DEFAULT_CHARS_PER_LINE),
    }

    width_in, height_in = _get_slide_dimensions(config)
    prs = Presentation()
    prs.slide_width = Inches(width_in)
    prs.slide_height = Inches(height_in)

    total_slides = 0

    for bloc in blocs:
        t = bloc.get("type", "")

        if t == "lecture":
            label = clean_spaces(bloc.get("intro_lue") or bloc.get("reference") or "Lecture")
            pages = split_text_for_slides(_strip_html(bloc.get("contenu", "")), **split_kwargs)
        elif t == "chant":
            label = clean_spaces(bloc.get("titre", "Chant"))
            pages = _chant_pages(bloc, split_kwargs)
        elif t == "message":
            label = clean_spaces(bloc.get("titre", "Message"))
            pages = split_text_for_slides(_strip_html(bloc.get("contenu", "")), **split_kwargs)
        else:
            continue

        y = len(pages)
        total_slides += y
        print(f"[pptx] {label} : {y} slide(s) générée(s)", flush=True)

        for x, page in enumerate(pages, start=1):
            _add_slide(prs, config, f"{label} - {x}/{y}", page, slide_type=t)

    print(f"[pptx] Total : {total_slides} slide(s)", flush=True)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))
    return output_path
