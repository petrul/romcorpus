# -*- coding: utf-8 -*-
import re, unicodedata

CYR_NUM = {
    'а':1,'в':2,'г':3,'д':4,'е':5,'ѕ':6,'з':7,'и':8,'ѳ':9,
    'і':10,'к':20,'л':30,'м':40,'н':50,'ѯ':60,'о':70,'п':80,
    'ч':90,'р':100,'с':200,'т':300,'у':400,'ф':500,'х':600,
    'ѱ':700,'ѡ':800,'ц':900,
}
CYR_FRONT = set('еиіїѣѥ')  # triggers ч -> c (soft) rather than ci

SIMPLE = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ж':'j','з':'z',
    'и':'i','і':'i','ї':'i','й':'i','i':'i','к':'k','л':'l','м':'m','н':'n',
    'о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h',
    'ц':'ț','ш':'ș','щ':'șt','ю':'iu','я':'ea','ё':'io','є':'ie',
    'ѡ':'o','ѣ':'e','ѥ':'ie','ѧ':'ea','ѳ':'t','ѵ':'i','ꙁ':'z',
    'ꙋ':'u','ꙑ':'î','ꙫ':'o','ы':'î','ѕ':'s','α':'a',
    'ẽ':'e','ủ':'u','ạ':'a','ᾱ':'a','ӯ':'u',
}

def _selective_nfd(raw):
    # Only decompose actual Latin-script letters (the ad-hoc proxy chars typed during
    # transcription, e.g. é, á). Cyrillic letters like й (=и + breve canonically) must
    # stay atomic, or the breve gets mistaken for a scribal titlo/tilde downstream.
    out = []
    for ch in raw:
        if 0x00C0 <= ord(ch) <= 0x1FFF and not (0x0400 <= ord(ch) <= 0x052F):
            out.append(unicodedata.normalize('NFD', ch))
        else:
            out.append(ch)
    return ''.join(out)

def preprocess(raw):
    raw = _selective_nfd(raw)
    # оу digraph (+ any combining marks anywhere inside) means plain /u/: fold to a single
    # already-mapped placeholder letter (ꙋ) so it flows through SIMPLE normally.
    raw = re.sub(r'[оО](?:[̀-ͯ҃])*[уУ](?:[̀-ͯ҃])*', 'ꙋ', raw)
    return raw

VOWELS = set('аеиіїоуѣѥѧѫꙗꙋꙑꙫюяєёẽủạᾱαѡ')
# Real titlo (U+0483) is an unambiguous abbreviation/numeral signal wherever it appears.
# Combining tilde (U+0303) was used two ways during transcription: over a CONSONANT it
# marks the same sacred-name abbreviation (iс̃, хс̃) as titlo; over a VOWEL it was used
# inconsistently as a decorative/stress mark, not a numeral signal, and is dropped.
# Combining acute (stress), breve, diaeresis etc. are always decorative and dropped.

def strip_marks(raw):
    # Combining marks in Unicode modify the PRECEDING base letter.
    letters = []
    marks = []
    for ch in raw:
        if ch == '҃':
            if marks:
                marks[-1] = True
            continue
        if ch == '̃':
            if marks and letters[-1].lower() not in VOWELS:
                marks[-1] = True
            continue
        if unicodedata.combining(ch):
            continue  # stress accent etc. — drop silently, not a titlo signal
        letters.append(ch)
        marks.append(False)
    return letters, marks

I_EQUIV = {'i': 'і', 'і': 'і', 'и': 'і', 'ї': 'і'}  # canonicalize i-lookalikes for word-identity checks only

def translit_word(raw0):
    raw = preprocess(raw0)
    letters, marks = strip_marks(raw)
    lraw = [l.lower() for l in letters]

    canon = ''.join(I_EQUIV.get(l, l) for l in lraw)
    if canon == 'іс' and any(marks):
        return 'Is'
    if canon == 'хс' and any(marks):
        return 'Hs'

    if any(marks) and lraw and len(lraw) <= 4 and all((l in CYR_NUM) for l in lraw):
        total = sum(CYR_NUM[l] for l in lraw)
        if total > 0:
            return str(total)

    out = []
    n = len(lraw)
    for i, l in enumerate(lraw):
        nxt = lraw[i+1] if i+1 < n else ''
        is_last = (i == n-1)
        if l == 'ъ':
            if not is_last:
                out.append('ă')
            continue
        if l == 'ь':
            out.append("'")
            continue
        if l == 'ꙗ':
            out.append('ă')
            continue
        if l == 'ѫ':
            out.append('î' if i == 0 else 'â')
            continue
        if l == 'ч':
            out.append('c' if (nxt in CYR_FRONT or nxt == '') else 'ci')
            continue
        if l in SIMPLE:
            out.append(SIMPLE[l])
            continue
        if l.isascii() and l.isalpha():
            out.append(l)  # plain Latin letter (from NFD-decomposed ad-hoc proxy chars) passes through
            continue
        out.append('{' + l + '}')
    return ''.join(out)

WORD_RE = re.compile(
    '[a-zA-ZÀ-ÿЀ-ӿ҃Ꙁ-ꚟ'
    'Ḁ-ỿἀ-῿̀-ͯ]+',
    re.UNICODE)

# A handful of one-off stray characters typed during transcription (visual
# slips, not part of any consistent convention) — normalized to their
# evident intent before word-matching runs.
STRAY_FIXUPS = {
    'vĩ': 'в҃і҃',   # "vĩ" (12 baskets, Matt 14:20) -> numeral в+і with titlo = 12
    'ĩ': 'і҃',           # bare "ĩ" numeral-10 marker -> і with titlo
    'ɪ': 'i',                 # IPA small-capital I slip -> plain i
    'چ': 'de',                # stray Arabic letter slip -> "de"
    'ℨ': 'z',                 # black-letter Z slip -> z
}

def translit_text(s):
    for bad, good in STRAY_FIXUPS.items():
        s = s.replace(bad, good)
    return WORD_RE.sub(lambda m: translit_word(m.group(0)), s)

if __name__ == '__main__':
    tests = ['домноу̃ль','фечорь','конецъ','iс̃','хс̃','кꙗ̃','съблꙗ̃знй̃те','ръспоу̃нсе',
              'сꙋ̃нть','ѫ','ѕ҃','вꙗ̃','нѣ','пꙗ̃мꙗ̃нть','мꙗ̃нꙗ̃нкꙗ̃','нꙗ̃родоу̃',
              'кꙋ̃носкоу̃ть','четврꙗ̃токь','въсẽ́хь','лꙗ̃сацн']
    for w in tests:
        print(w, '->', translit_word(w))
