"""Ready-to-edit templates and safe LaTeX generators."""
import hashlib
import sys
from pathlib import Path


def preview_asset(root, source, extension):
    key = hashlib.sha256(source.encode('utf-8')).hexdigest()
    asset_root = Path(getattr(sys, '_MEIPASS', root))
    path = asset_root / 'assets' / 'templates' / (key + extension)
    return path if path.is_file() else None


def escape_text(value):
    replacements = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(replacements.get(c, c) for c in value)


def document(title, body, kind='article'):
    return '\\documentclass[12pt]{' + kind + '}\n' + r'''\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\setlength{\textwidth}{16cm}
\setlength{\oddsidemargin}{0cm}
\setlength{\textheight}{23cm}
\usepackage{graphicx}
\title{''' + title + r'''}
\author{Votre nom}
\date{\today}
\begin{document}
\maketitle
''' + body + '\n\\end{document}\n'


EXTRA_TEMPLATES = {
    'CV': document('Curriculum vitae', r'''\section*{Contact}
Nom Prénom — email@example.com — Téléphone
\section*{Profil}
Présentez votre parcours et votre objectif.
\section*{Formation}
Diplôme, établissement, année.
\section*{Expérience}
Poste, entreprise, dates et réalisations.
\section*{Compétences}
Langues, outils et compétences techniques.'''),
    'Mémoire / Thèse': document('Titre du mémoire', r'''\tableofcontents
\chapter{Introduction}
Contexte, problématique et objectifs.
\chapter{État de l’art}
Travaux existants et références.
\chapter{Méthodologie}
Votre démarche.
\chapter{Résultats}
Analyse et discussion.
\chapter{Conclusion}
Bilan et perspectives.''', 'report'),
    'Rapport de stage': document('Rapport de stage', r'''\tableofcontents
\chapter{Présentation de l’entreprise}
Entreprise, équipe et contexte.
\chapter{Missions réalisées}
Objectifs, outils et réalisations.
\chapter{Bilan}
Compétences acquises et conclusion.''', 'report'),
    'Examen': document('Examen — Matière', r'''Durée : 2 heures \hfill Nom : \dotfill
\section*{Exercice 1 — 10 points}
\begin{enumerate}
\item Première question.
\item Deuxième question.
\end{enumerate}
\section*{Exercice 2 — 10 points}
Énoncé de l’exercice.'''),
    'العربية — Article': r'''\documentclass[12pt]{article}
% Compile with XeLaTeX. Arial supports Arabic and is available on Windows.
\setlength{\textwidth}{16cm}
\setlength{\oddsidemargin}{0cm}
\setlength{\textheight}{23cm}
\usepackage{fontspec}
\usepackage{polyglossia}
\setdefaultlanguage{arabic}
\setotherlanguage{french}
\newfontfamily\arabicfont[Script=Arabic]{Arial}
\newfontfamily\frenchfont{Arial}
\title{عنوان الوثيقة}
\author{اسم الكاتب}
\date{}
\begin{document}
\maketitle
\section{مقدمة}
هذا نموذج لكتابة وثيقة باللغة العربية. اكتب النص هنا.
\section{المحتوى}
يمكن إضافة الصور والجداول والمعادلات.
\begin{french}Texte en français.\end{french}
\end{document}
''',
}

DESCRIPTIONS = {'Article': 'Texte, sections et équations', 'Document vide': 'Commencer de zéro', 'Rapport': 'Chapitres et sommaire', 'Présentation': 'Diapositives Beamer', 'CV': 'Profil, formation et expérience', 'Mémoire / Thèse': 'Recherche et résultats', 'Rapport de stage': 'Entreprise, missions et bilan', 'Examen': 'Exercices et questions', 'العربية — Article': 'العربية · RTL · XeLaTeX'}


def table_source(cells, caption=''):
    if not cells or not cells[0] or any(len(row) != len(cells[0]) for row in cells):
        raise ValueError('Le tableau doit être rectangulaire.')
    result = '\\begin{table}[ht]\n\\centering\n'
    if caption.strip():
        result += '\\caption{' + escape_text(caption) + '}\n'
    result += '\\begin{tabular}{|' + '|'.join('l' for _ in cells[0]) + '|}\n\\hline\n'
    for row in cells:
        result += ' & '.join(escape_text(cell) for cell in row) + r' \\' + '\n\\hline\n'
    return result + '\\end{tabular}\n\\end{table}\n'
