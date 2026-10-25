#!/usr/bin/env python3
"""Gera os SVGs animados do README do perfil, em tema claro e escuro.

O texto vira traço (path) com as mesmas fontes do portfólio, então o SVG não depende de fonte instalada
e as animações são CSS dentro do próprio arquivo (o GitHub permite <style> em SVG).

Uso:
    pip install fonttools uharfbuzz
    python3 assets/src/gen.py

As fontes (licença OFL) são baixadas do repositório google/fonts na primeira execução.
Para mudar textos, projetos ou a stack, edite as constantes abaixo e rode de novo.
"""
import json
import os
import urllib.request
from pathlib import Path

import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.svgPathPen import SVGPathPen

SRC = Path(__file__).resolve().parent
OUT = SRC.parent
FONTS = Path(os.environ.get('FONTS_DIR', Path.home() / '.cache' / 'perfil-fontes'))
GF = 'https://raw.githubusercontent.com/google/fonts/main/ofl/'
FONT_URLS = {
    'Archivo[wdth,wght].ttf': GF + 'archivo/Archivo%5Bwdth,wght%5D.ttf',
    'IBMPlexSans[wdth,wght].ttf': GF + 'ibmplexsans/IBMPlexSans%5Bwdth,wght%5D.ttf',
    'IBMPlexMono-Regular.ttf': GF + 'ibmplexmono/IBMPlexMono-Regular.ttf',
    'IBMPlexMono-Medium.ttf': GF + 'ibmplexmono/IBMPlexMono-Medium.ttf',
}


def font_file(name):
    p = FONTS / name
    if not p.exists():
        FONTS.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(FONT_URLS[name], p)
    return p


class PathFont:
    """Uma fonte numa instância fixa (largura/peso): HarfBuzz para o espaçamento, fontTools para os contornos."""

    def __init__(self, file, axes, prefix):
        path = font_file(file)
        tt = TTFont(path)
        if axes and 'fvar' in tt:
            tt = instancer.instantiateVariableFont(tt, axes)
        self.prefix = prefix
        self.upm = tt['head'].unitsPerEm
        self.order = tt.getGlyphOrder()
        self.gs = tt.getGlyphSet()
        self.hbfont = hb.Font(hb.Face(path.read_bytes()))
        if axes:
            self.hbfont.set_variations(axes)
        self.cache = {}

    def path(self, gn):
        if gn not in self.cache:
            pen = SVGPathPen(self.gs)
            self.gs[gn].draw(pen)
            self.cache[gn] = pen.getCommands()
        return self.cache[gn]

    def shape(self, s):
        buf = hb.Buffer()
        buf.add_str(s)
        buf.guess_segment_properties()
        hb.shape(self.hbfont, buf, {'kern': True})
        return [(i.codepoint, p.x_advance, p.x_offset, p.y_offset) for i, p in zip(buf.glyph_infos, buf.glyph_positions)]

    def width(self, s, size, tracking=0.0):
        g = self.shape(s)
        return (sum(x[1] for x in g) + tracking * self.upm * max(len(g) - 1, 0)) * size / self.upm


class Doc:
    """Um SVG: registra os glifos usados e gera o <defs> só com eles (cada letra é desenhada uma vez)."""

    def __init__(self):
        self.used = {}

    def ref(self, pf, gn):
        key = (pf.prefix, gn)
        if key not in self.used:
            self.used[key] = (pf, gn, f'{pf.prefix}{len(self.used)}')
        return self.used[key][2]

    def text(self, pf, s, x, y, size, fill, tracking=0.0, anchor='start', letters=None):
        """letters=(atraso inicial, intervalo): cada letra ganha a classe "lt" com seu próprio atraso."""
        sc = size / pf.upm
        g = pf.shape(s)
        trk = tracking * pf.upm
        w = (sum(a[1] for a in g) + trk * max(len(g) - 1, 0)) * sc
        if anchor == 'end':
            x -= w
        elif anchor == 'middle':
            x -= w / 2
        cx, uses, k = 0, [], 0
        for gid, adv, xo, yo in g:
            gn = pf.order[gid]
            if pf.path(gn):
                extra = ''
                if letters:
                    extra = f' class="lt" style="animation-delay:{letters[0] + k * letters[1]:.3f}s"'
                    k += 1
                uses.append(f'<use xlink:href="#{self.ref(pf, gn)}" x="{cx + xo:.0f}" y="{yo:.0f}"{extra}/>')
            cx += adv + trk
        return f'<g fill="{fill}" transform="translate({x:.2f} {y:.2f}) scale({sc:.6f} {-sc:.6f})">{"".join(uses)}</g>', w

    def defs(self):
        return ''.join(f'<path id="{i}" d="{pf.path(gn)}"/>' for pf, gn, i in self.used.values())


def wrap(pf, s, size, maxw, max_lines=2):
    lines, cur = [], ''
    for word in s.split():
        t = (cur + ' ' + word).strip()
        if pf.width(t, size) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        raise ValueError(f'o texto não cabe em {max_lines} linhas: {s!r}')
    return lines


def svg(w, h, title, css, body, doc):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{title}">'
            f'<title>{title}</title><style>{css}</style><defs>{doc.defs()}</defs>{body}</svg>')


ARCH = PathFont('Archivo[wdth,wght].ttf', {'wdth': 125, 'wght': 850}, 'a')
ARCH2 = PathFont('Archivo[wdth,wght].ttf', {'wdth': 112, 'wght': 780}, 'b')
SANS = PathFont('IBMPlexSans[wdth,wght].ttf', {'wdth': 100, 'wght': 400}, 's')
SANSB = PathFont('IBMPlexSans[wdth,wght].ttf', {'wdth': 100, 'wght': 600}, 't')
MONO = PathFont('IBMPlexMono-Regular.ttf', None, 'm')
MONOM = PathFont('IBMPlexMono-Medium.ttf', None, 'n')

# mesmas cores do portfólio (braganux.github.io)
THEMES = {
    'light': dict(card='#EDEFF3', surface='#F8F9FB', ink='#11151F', muted='#586174', faint='#8A93A4', line='#D2D8E1',
                  accent='#2A44D2', accentSoft='#E0E5FB', onAccent='#FFFFFF', gold='#8A5F00', goldSoft='#F6EAC4',
                  ok='#1C9A5E', lane='#C3CAD6',
                  cs='#6B48D6', ts='#2F74E0', dart='#14A0C2', rust='#CF5F33', go='#22A486', js='#D4AA12', py='#3C8A4B',
                  sql='#8B6A50', html='#CF4377', java='#B03838', asm='#5F6B7D', docs='#9AA2B1'),
    'dark': dict(card='#10141D', surface='#161B27', ink='#E7EAF1', muted='#9AA3B6', faint='#6E788C', line='#283044',
                 accent='#8FA2FF', accentSoft='#1E2754', onAccent='#0D1018', gold='#EFC253', goldSoft='#34290F',
                 ok='#3CCB86', lane='#2C3549',
                 cs='#8B6CF0', ts='#5591F0', dart='#2CB6D6', rust='#E07447', go='#35BE9C', js='#E3BC2A', py='#52A862',
                 sql='#A6846A', html='#E25C8E', java='#D25454', asm='#8C97AA', docs='#5B6477'),
}
LANGKEY = {'C#': 'cs', 'TypeScript': 'ts', 'Dart': 'dart', 'Rust': 'rust', 'Go': 'go', 'JavaScript': 'js', 'Python': 'py',
           'SQL': 'sql', 'HTML/CSS': 'html', 'Java': 'java', 'Assembly': 'asm', 'Docs': 'docs'}
# participação de cada linguagem em 1.380 arquivos de código dos repositórios (inclui projetos em equipe)
LANG_SHARE = [('C#', 18.4, 'cs'), ('TypeScript', 17.2, 'ts'), ('Dart', 11.2, 'dart'), ('Rust', 9.7, 'rust'),
              ('Python', 9.4, 'py'), ('Go', 8.3, 'go'), ('JavaScript', 7.5, 'js'), ('SQL', 5.9, 'sql'),
              ('HTML/CSS', 4.7, 'html'), ('Java', 4.6, 'java'), ('outras', 3.1, 'asm')]
LANG_FILES = '1.380 arquivos'

BASE_CSS = ('@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}'
            '@keyframes fade{from{opacity:0}to{opacity:1}}'
            '@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}'
            '@keyframes pop{from{opacity:0;transform:scale(.3)}to{opacity:1;transform:none}}'
            '.rise{animation:rise .7s cubic-bezier(.2,.8,.2,1) both}.fade{animation:fade .8s ease both}'
            '.grow{transform-box:fill-box;transform-origin:0 50%;animation:grow .9s cubic-bezier(.2,.8,.2,1) both}'
            '.pop{transform-box:fill-box;transform-origin:center;animation:pop .45s cubic-bezier(.2,.8,.2,1) both}')
REDUCE = '@media (prefers-reduced-motion:reduce){.rise,.fade,.grow,.pop{animation:none}}'


def delay(s):
    return f' style="animation-delay:{s:.2f}s"'


def lang_bar(parts, x, y, w, h, T, base_delay=0.0):
    out, cx, total = [], x, sum(p[1] for p in parts)
    for i, (_, p, k) in enumerate(parts):
        ww = w * p / total if i < len(parts) - 1 else x + w - cx
        out.append(f'<rect class="grow"{delay(base_delay + i * 0.07)} x="{cx:.2f}" y="{y}" width="{ww:.2f}" height="{h}" fill="{T[k]}"/>')
        cx += ww
    return ''.join(out)


# ---------------------------------------------------------------- cabeçalho
EYEBROW = 'DESENVOLVEDOR FULL-STACK · SANTA MARIA, RS'
SITE = 'braganux.github.io'
PHRASES = ['do banco de dados ao app no celular', 'C#, .NET, Flutter e React no dia a dia',
           'sócio-fundador de uma startup incubada', 'prêmio de melhor usabilidade no Code Race']
NOW = [('Forza Clubes', 'Desenvolvedor full-stack desde 2024'),
       ('3Summa', 'Sócio-fundador, produto incubado no InovAMF'),
       ('Antonio Meneghetti Faculdade', 'Sistemas de Informação, TCC em nov/2026')]
TYPE, HOLD, ERASE, SLOT = 1.4, 3.7, 4.2, 4.5  # segundos dentro do tempo de cada frase
GAP = 1.0  # pausa com o cursor piscando no início de cada volta (e na abertura)


def header(theme):
    T, d = THEMES[theme], Doc()
    W, H, P = 1000, 340, 44
    b = [f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="{T["card"]}" stroke="{T["line"]}"/>']
    g, _ = d.text(MONOM, EYEBROW, P, 66, 13.5, T['muted'], tracking=0.08)
    b.append(f'<g class="fade">{g}</g>')
    g, _ = d.text(MONOM, SITE + ' ↗', W - P, 66, 13.5, T['accent'], anchor='end')
    b.append(f'<g class="fade"{delay(.3)}>{g}</g>')
    size = 90
    while max(ARCH.width('BRAYAN', size, -0.02), ARCH.width('MARTINS', size, -0.02)) > 500:
        size -= 1
    g1, _ = d.text(ARCH, 'BRAYAN', P - 3, 158, size, T['ink'], tracking=-0.02, letters=(.05, .05))
    g2, _ = d.text(ARCH, 'MARTINS', P - 3, 240, size, T['accent'], tracking=-0.02, letters=(.22, .05))
    b.append(g1 + g2)

    # frases sendo digitadas: uma tarja da cor do fundo cobre o texto e anda uma letra por vez
    fs, y0 = 18, 288
    pg, pw = d.text(MONOM, '>', P, y0, fs, T['accent'])
    b.append(f'<g class="fade"{delay(.5)}>{pg}</g>')
    x0 = P + pw + 12
    cw = MONO.width('a', fs)
    cyc = GAP + SLOT * len(PHRASES)
    pct = lambda s: f'{s / cyc * 100:.2f}%'
    caret = f'<rect class="caret" x="{x0:.1f}" y="{y0 - 15}" width="2.4" height="19" fill="{T["accent"]}"/>'
    css = [f'@keyframes gap{{0%{{opacity:1}}{pct(GAP - .01)}{{opacity:1}}{pct(GAP)},100%{{opacity:0}}}}'
           f'.gap{{animation:gap {cyc:g}s linear infinite}}']
    b.append(f'<g class="gap" opacity="0">{caret}</g>')
    for i, ph in enumerate(PHRASES):
        n, tw = len(ph), cw * len(ph)
        tg, _ = d.text(MONO, ph, x0, y0, fs, T['ink'])
        t0 = GAP + i * SLOT
        st = f'animation-timing-function:steps({n},end)'
        css.append(f'@keyframes s{i}{{0%{{opacity:0}}{pct(t0 - .01)}{{opacity:0}}{pct(t0)}{{opacity:1}}'
                   f'{pct(t0 + SLOT - .01)}{{opacity:1}}{pct(t0 + SLOT)},100%{{opacity:0}}}}'
                   f'@keyframes c{i}{{0%{{transform:translateX(0)}}{pct(t0)}{{transform:translateX(0);{st}}}'
                   f'{pct(t0 + TYPE)}{{transform:translateX({tw:.1f}px)}}{pct(t0 + HOLD)}{{transform:translateX({tw:.1f}px);{st}}}'
                   f'{pct(t0 + ERASE)},100%{{transform:translateX(0)}}}}'
                   f'.ph{i}{{animation:s{i} {cyc:g}s linear infinite}}.cv{i}{{animation:c{i} {cyc:g}s ease infinite}}')
        # sem animação (leitores estáticos, movimento reduzido) fica só a primeira frase, inteira
        hidden = ' opacity="0"' if i else ''
        shown = f' transform="translate({tw:.1f} 0)"' if i == 0 else ''
        b.append(f'<g class="ph ph{i}"{hidden}>{tg}<g class="cv cv{i}"{shown}>'
                 f'<rect x="{x0 - 1:.1f}" y="{y0 - 18}" width="{tw + 24:.1f}" height="26" fill="{T["card"]}"/>{caret}</g></g>')
    css.append('@keyframes blink{50%{opacity:0}}.caret{animation:blink 1s steps(1) infinite}')
    css.append('@keyframes ping{0%{transform:scale(1);opacity:.85}80%,100%{transform:scale(2.9);opacity:0}}'
               '.pulse{transform-box:fill-box;transform-origin:center;animation:ping 2.4s cubic-bezier(0,0,.2,1) infinite}')
    css.append('@keyframes lt{from{opacity:0;transform:translateY(-150px)}to{opacity:1;transform:none}}'
               '.lt{animation:lt .65s cubic-bezier(.2,.8,.2,1) both}')
    css.append('@media (prefers-reduced-motion:reduce){.gap,.ph,.cv,.caret,.pulse,.lt{animation:none}.pulse{opacity:0}}')

    # coluna "agora"
    cx = 620
    b.append(f'<line class="fade"{delay(.35)} x1="{cx - 26}" y1="94" x2="{cx - 26}" y2="250" stroke="{T["line"]}"/>')
    g, _ = d.text(MONOM, 'AGORA', cx + 15, 104, 11.5, T['muted'], tracking=0.12)
    rows = [f'<circle class="pulse" cx="{cx + 4}" cy="100" r="4" fill="none" stroke="{T["ok"]}" stroke-width="1.6"/>'
            f'<circle cx="{cx + 4}" cy="100" r="4" fill="{T["ok"]}"/>', g]
    for j, (t1, t2) in enumerate(NOW):
        yy = 142 + j * 46
        rows.append(d.text(SANSB, t1, cx, yy, 16, T['ink'])[0] + d.text(SANS, t2, cx, yy + 20, 14, T['muted'])[0])
    b.append(f'<g class="fade"{delay(.45)}>{"".join(rows)}</g>')
    b.append(lang_bar(LANG_SHARE, P, 310, W - 2 * P, 8, T, base_delay=.6))
    title = 'Brayan Martins, desenvolvedor full-stack em Santa Maria, RS'
    return svg(W, H, title, BASE_CSS + ''.join(css) + REDUCE, ''.join(b), d)


# ---------------------------------------------------------------- cards de projeto
# (arquivo, nome, selo, é prêmio?, descrição em até 2 linhas, stack, linguagens no código)
CARDS = [
    ('panela', 'Panela', 'TCC · 2025–2026', False,
     'Divide as despesas do grupo e ajuda a planejar antes de gastar, com acerto via Pix e resumo por IA.',
     'Flutter · ASP.NET Core · PostgreSQL · Firebase', [('', 53.7, 'dart'), ('', 25.4, 'cs'), ('', 16.7, 'ts'), ('', 2.4, 'js'), ('', 1.8, 'html')]),
    ('3summa', '3Summa', 'Incubado · InovAMF', False,
     'Produto para a área contábil, com atendimento pelo WhatsApp, inbox da equipe e controle de custos.',
     'React · TypeScript · Rust (Axum) · PostgreSQL', [('', 46.5, 'rust'), ('', 36.5, 'ts'), ('', 14.5, 'sql'), ('', 2.5, 'html')]),
    ('nexa-solution', 'SaaS para o agro', 'Melhor usabilidade · Code Race', True,
     'Gestão para a cadeia do agro, da equipe Nexa Solution, com agente de IA no WhatsApp e busca semântica.',
     'LangChain · pgvector · Django → Rust · React', [('', 37.3, 'rust'), ('', 26.4, 'ts'), ('', 21.8, 'py'), ('', 11.8, 'sql'), ('', 2.7, 'js')]),
    ('up-espaco', 'Up Espaço', 'Em equipe · PO e front-end', False,
     'Conecta equipe e famílias num espaço de desenvolvimento infantil, com Clean Architecture e observabilidade.',
     'Go · React · PostgreSQL · Prometheus · Grafana', [('', 66.1, 'go'), ('', 20.7, 'sql'), ('', 9.2, 'js'), ('', 2.9, 'asm'), ('', 1.1, 'html')]),
    ('bookguess', 'BookGuess', 'IA · RAG', False,
     'Wordle literário com dicas geradas por IA usando RAG e ranking em tempo real.',
     '.NET · Next.js · FastAPI · pgvector · Redis', [('', 52.9, 'cs'), ('', 18.2, 'py'), ('', 12.3, 'ts'), ('', 10.7, 'html'), ('', 4.3, 'js'), ('', 1.6, 'asm')]),
    ('ecoscan', 'EcoScan', 'Visão computacional', False,
     'Classifica o lixo em 12 categorias pela câmera, com cerca de 92% de acurácia, para rodar no Raspberry Pi.',
     'TensorFlow · MobileNetV2 · OpenCV', [('', 100, 'py')]),
]


def card(theme, c):
    key, name, badge, prize, desc, stack_txt, langs = c
    T, d = THEMES[theme], Doc()
    W, H, P = 480, 196, 24
    b = [f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="{T["card"]}" stroke="{T["line"]}"/>']
    bw = MONOM.width(badge.upper(), 11.5, 0.07) + 16
    bg, fg = (T['goldSoft'], T['gold']) if prize else (T['accentSoft'], T['accent'])
    g, _ = d.text(MONOM, badge.upper(), P + 8, P + 16, 11.5, fg, tracking=0.07)
    b.append(f'<g class="fade"><rect x="{P}" y="{P}" width="{bw:.1f}" height="23" rx="3" fill="{bg}"/>{g}</g>')
    b.append(f'<g class="fade"{delay(.4)}>{d.text(MONOM, "↗", W - P, P + 16, 15, T["muted"], anchor="end")[0]}</g>')
    g, _ = d.text(ARCH2, name, P - 1, P + 64, 30, T['ink'], tracking=-0.01)
    b.append(f'<g class="rise"{delay(.08)}>{g}</g>')
    lines = wrap(SANS, desc, 15, W - 2 * P)
    gl = ''.join(d.text(SANS, ln, P, P + 94 + k * 21, 15, T['muted'])[0] for k, ln in enumerate(lines))
    b.append(f'<g class="fade"{delay(.2)}>{gl}</g>')
    g, _ = d.text(MONO, stack_txt, P, H - 34, 13, T['faint'] if theme == 'light' else T['muted'])
    b.append(f'<g class="fade"{delay(.3)}>{g}</g>')
    b.append(lang_bar(langs, P, H - 22, W - 2 * P, 5, T, base_delay=.35))
    return svg(W, H, f'{name}: {desc}', BASE_CSS + REDUCE, ''.join(b), d)


# ---------------------------------------------------------------- trajetória
# cada repositório: mês da última atualização, linguagem principal e se está em destaque
REPOS = json.loads((SRC / 'trajetoria.json').read_text(encoding='utf-8'))
LANES = [('Exército Brasileiro', '2021-03', '2022-02', False), ('Logística · Modo Logística', '2022-05', '2024-08', False),
         ('Sistemas de Informação · AMF', '2022-02', '2026-11', False),
         ('Desenvolvedor full-stack · Forza Clubes', '2024-07', '2026-10', True)]
TODAY = '2026-10'
LEGEND = [('Python', 'py'), ('Documentação', 'docs'), ('JavaScript', 'js'), ('Java', 'java'), ('TypeScript', 'ts'),
          ('C#', 'cs'), ('Rust', 'rust'), ('Dart', 'dart'), ('Go', 'go'), ('HTML/CSS', 'html'), ('Assembly', 'asm')]


def mi(s):
    y, m = map(int, s.split('-'))
    return (y - 2021) * 12 + (m - 1)


def trajetoria(theme):
    T, d = THEMES[theme], Doc()
    W, P = 1000, 28
    pw = W - 2 * P
    months = 72
    bwid = pw / months
    r, step = 5.4, 2 * 5.4 + 2.2
    bins = {}
    for rp in sorted(REPOS, key=lambda x: x['d']):
        bins.setdefault(mi(rp['d']), []).append(rp)
    maxs = max(len(v) for v in bins.values())
    top = 78
    axis = top + maxs * step + 8
    lane_top, gap = axis + 46, 34
    lane_end = lane_top + (len(LANES) - 1) * gap
    leg1, leg2 = lane_end + 64, lane_end + 90
    H = leg2 + 26
    xm = lambda m: P + m / months * pw
    first, last = min(x['d'] for x in REPOS)[:4], max(x['d'] for x in REPOS)[:4]
    b = [f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="{T["card"]}" stroke="{T["line"]}"/>']
    g, _ = d.text(ARCH2, 'Repositórios no tempo', P, 46, 24, T['ink'])
    g2, _ = d.text(MONO, f'{len(REPOS)} repositórios de {first} a {last}', W - P, 45, 13, T['muted'], anchor='end')
    b.append(f'<g class="fade">{g}{g2}</g>')
    b.append(f'<line x1="{P}" x2="{W - P}" y1="{axis}" y2="{axis}" stroke="{T["line"]}"/>')
    for yv in range(2021, 2027):
        x = xm((yv - 2021) * 12)
        b.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{axis}" y2="{axis + 6}" stroke="{T["line"]}"/>')
        b.append(d.text(MONO, str(yv), x + 4, axis + 20, 12, T['muted'])[0])
    xn = xm(mi(TODAY) + .5)
    b.append(f'<g class="fade"{delay(2.4)}><line x1="{xn:.1f}" x2="{xn:.1f}" y1="{top - 8}" y2="{lane_end + 18}" '
             f'stroke="{T["accent"]}" stroke-dasharray="3 4"/>{d.text(MONOM, "hoje", xn - 7, lane_end + 31, 12, T["accent"], anchor="end")[0]}</g>')
    for i, (t, a, z, acc) in enumerate(LANES):
        ly = lane_top + i * gap
        x1, x2 = xm(mi(a)), xm(mi(z) + 1)
        b.append(f'<rect class="grow"{delay(.3 + i * .15)} x="{x1:.1f}" y="{ly}" width="{x2 - x1:.1f}" height="7" rx="3.5" '
                 f'fill="{T["accent"] if acc else T["lane"]}"/>')
        b.append(f'<g class="fade"{delay(.4 + i * .15)}>{d.text(MONO, t, x1, ly - 8, 12.5, T["ink"])[0]}</g>')
    idx = 0
    for m in sorted(bins):
        cx = P + (m + .5) * bwid
        for k, rp in enumerate(bins[m]):
            cy = axis - 6 - r - k * step
            col = T[LANGKEY.get(rp['l'], 'docs')]
            ring = (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r + 2.6}" fill="none" stroke="{T["ink"]}" stroke-width="1.4"/>'
                    if rp.get('destaque') else '')
            b.append(f'<g class="pop"{delay(.6 + idx * .045)}>{ring}'
                     f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{col}" stroke="{T["card"]}" stroke-width="1.4"/></g>')
            idx += 1
    # legenda: linguagens com a contagem de repositórios
    counts = {}
    for rp in REPOS:
        k = LANGKEY.get(rp['l'], 'docs')
        counts[k] = counts.get(k, 0) + 1
    items = [(f'{nm} {counts[k]}', k) for nm, k in LEGEND if counts.get(k)]
    fs = 12.5
    widths = [13 + MONO.width(lab, fs) for lab, _ in items]
    gap_x = min(18, (pw - sum(widths)) / (len(items) - 1))
    x, leg = P, []
    for (lab, k), w in zip(items, widths):
        leg.append(f'<circle cx="{x + 4.5:.1f}" cy="{leg1 - 4}" r="4.5" fill="{T[k]}"/>' + d.text(MONO, lab, x + 13, leg1, fs, T['muted'])[0])
        x += w + gap_x
    leg.append(f'<circle cx="{P + 4.5:.1f}" cy="{leg2 - 4}" r="4.5" fill="none" stroke="{T["ink"]}" stroke-width="1.4"/>'
               + d.text(MONO, 'em destaque no perfil', P + 14, leg2, fs, T['muted'])[0])
    note = 'cada ponto é um repositório, no mês da última atualização e na cor da linguagem principal'
    leg.append(d.text(MONO, note, W - P, leg2, fs, T['faint'] if theme == 'light' else T['muted'], anchor='end')[0])
    b.append(f'<g class="fade"{delay(2.6)}>{"".join(leg)}</g>')
    title = (f'Trajetória: {len(REPOS)} repositórios de {first} a {last}, sobre as faixas de Exército, logística, '
             'faculdade e Forza Clubes')
    return svg(W, H, title, BASE_CSS + REDUCE, ''.join(b), d)


# ---------------------------------------------------------------- stack
DAILY = ['C#', '.NET', 'ASP.NET Core', 'Blazor', 'Flutter', 'React', 'TypeScript', 'MySQL', 'SVN', 'JWT']
PROJ_GROUPS = [('back-end e web', ['Go', 'Rust', 'Python', 'Java', 'FastAPI', 'Django', 'Node.js', 'Next.js']),
               ('dados e IA', ['PostgreSQL', 'pgvector', 'MongoDB', 'Redis', 'LangChain', 'TensorFlow', 'scikit-learn']),
               ('infra e ferramentas', ['Docker', 'Nginx', 'Kafka', 'Prometheus', 'Grafana', 'Git'])]
PROJ = [it for _, items in PROJ_GROUPS for it in items]


def stack(theme):
    T, d = THEMES[theme], Doc()
    W, P, LW = 1000, 28, 150
    x0, xr = P + LW, W - P
    b_rows, idx = [], 0

    # linguagens
    y = 30
    b_rows.append(f'<g class="fade">{d.text(MONOM, "LINGUAGENS", P, y + 10, 12, T["muted"], tracking=0.1)[0]}'
                  f'{d.text(MONO, LANG_FILES, P, y + 29, 12, T["faint"] if theme == "light" else T["muted"])[0]}</g>')
    b_rows.append(lang_bar(LANG_SHARE, x0, y + 1, xr - x0, 10, T, base_delay=.1))
    fs, x, yy = 12, x0, y + 35
    labs = []
    for nm, p, k in LANG_SHARE:
        lab = f'{nm} {str(p).replace(".", ",")}%'
        w = 12 + MONO.width(lab, fs)
        if x + w > xr:
            x, yy = x0, yy + 21
        labs.append(f'<circle cx="{x + 4:.1f}" cy="{yy - 4}" r="4" fill="{T[k]}"/>' + d.text(MONO, lab, x + 12, yy, fs, T['muted'])[0])
        x += w + 16
    b_rows.append(f'<g class="fade"{delay(.5)}>{"".join(labs)}</g>')
    y = yy + 22
    b_rows.append(f'<line x1="{P}" x2="{xr}" y1="{y}" y2="{y}" stroke="{T["line"]}"/>')
    y += 22

    def chips(items, x, yy, daily, idx):
        fill, stroke, fg = (T['accentSoft'], 'none', T['accent']) if daily else (T['surface'], T['line'], T['ink'])
        out = []
        for it in items:
            cw = MONO.width(it, 13) + 22
            out.append(f'<g class="fade"{delay(.15 + idx * .035)}><rect x="{x:.1f}" y="{yy}" width="{cw:.1f}" height="28" rx="4" '
                       f'fill="{fill}" stroke="{stroke}"/>{d.text(MONO, it, x + 11, yy + 18.5, 13, fg)[0]}</g>')
            x += cw + 8
            idx += 1
        return out, x - 8, idx

    b_rows.append(f'<g class="fade">{d.text(MONOM, "NO DIA A DIA", P, y + 18.5, 12, T["muted"], tracking=0.1)[0]}</g>')
    out, xe, idx = chips(DAILY, x0, y, True, idx)
    if xe > xr:
        raise ValueError('a stack do dia a dia não cabe numa linha')
    b_rows += out
    y += 28 + 22
    b_rows.append(f'<line x1="{P}" x2="{xr}" y1="{y}" y2="{y}" stroke="{T["line"]}"/>')
    y += 22
    b_rows.append(f'<g class="fade">{d.text(MONOM, "EM PROJETOS", P, y + 18.5, 12, T["muted"], tracking=0.1)[0]}</g>')
    for j, (group, items) in enumerate(PROJ_GROUPS):
        out, xe, idx = chips(items, x0, y, False, idx)
        lab, lw = d.text(MONO, group, xr, y + 18.5, 12, T['faint'] if theme == 'light' else T['muted'], anchor='end')
        if xe + 24 > xr - lw:
            raise ValueError(f'o grupo {group!r} não cabe numa linha')
        b_rows += out + [f'<g class="fade"{delay(.3 + j * .1)}>{lab}</g>']
        y += 28 + (10 if j < len(PROJ_GROUPS) - 1 else 0)
    H = y + 28
    b = [f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="{T["card"]}" stroke="{T["line"]}"/>'] + b_rows
    title = 'Stack. No dia a dia: ' + ', '.join(DAILY) + '. Em projetos: ' + ', '.join(PROJ)
    return svg(W, H, title, BASE_CSS + REDUCE, ''.join(b), d)


# ---------------------------------------------------------------- botões
BUTTONS = [('portfolio', 'Portfólio', True), ('linkedin', 'LinkedIn', False), ('instagram', 'Instagram', False),
           ('email', 'E-mail', False)]


def button(theme, label, primary):
    T, d = THEMES[theme], Doc()
    fs, H, pad = 12.5, 40, 18
    txt = label.upper()
    tw = MONOM.width(txt, fs, 0.08)
    aw = MONOM.width('↗', fs)
    W = round(pad + tw + 9 + aw + pad)
    if primary:
        bg = f'<rect width="{W}" height="{H}" rx="6" fill="{T["accent"]}"/>'
        fg = arrow = T['onAccent']
    else:
        bg = f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="6" fill="{T["surface"]}" stroke="{T["line"]}"/>'
        fg, arrow = T['ink'], T['accent']
    body = bg + d.text(MONOM, txt, pad, 24.4, fs, fg, tracking=0.08)[0] + d.text(MONOM, '↗', W - pad, 24.4, fs, arrow, anchor='end')[0]
    return svg(W, H, label, '', body, d)


def main():
    sizes = {}
    for th in THEMES:
        files = {f'header-{th}.svg': header(th), f'trajetoria-{th}.svg': trajetoria(th), f'stack-{th}.svg': stack(th)}
        for c in CARDS:
            files[f'card-{c[0]}-{th}.svg'] = card(th, c)
        for key, label, primary in BUTTONS:
            files[f'btn-{key}-{th}.svg'] = button(th, label, primary)
        for fn, content in files.items():
            (OUT / fn).write_text(content, encoding='utf-8')
            sizes[fn] = len(content.encode())
    for fn in sorted(sizes):
        print(f'{sizes[fn] / 1024:6.1f} KB  {fn}')


if __name__ == '__main__':
    main()
