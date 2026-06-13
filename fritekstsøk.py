import argparse
import csv
import functools
import itertools
import operator
import re
import requests
import sys


parser = argparse.ArgumentParser(
    description=('Visa leksem med og definisjonar som matchar eit fritekstsøk. '
                 'Bruker Ordbok API: https://ord.uib.no/ord_2_API.html\n \n'
                 'Brukseksempel:\n \n'
                 'python fritekstsøk.py -s \'stor liten\' \' --ordbok'),
    formatter_class=argparse.RawTextHelpFormatter,
    prog='fritekstsøk')
parser.add_argument('-s', '--søk', required=True, type=str, help='Søkjestrengen.')
parser.add_argument('-o', '--ordbok', type=str, choices=['bm', 'nn', 'bm,nn'],
                    default='bm,nn',
                    help='Ordbok/-bøkene som skal brukast. Default er båe to.')
parser.add_argument('--api', default='https://ord.uib.no',
                    help='API-et som skal brukast.')
parser.add_argument('-k', '--ordklasse',
                    choices=['ADJ', 'ADP', 'ADV', 'AUX', 'CCONJ', 'DET', 'INTJ',
                             'NOUN', 'NUM', 'PART', 'PRON', 'PROPN', 'PUNCT',
                             'SCONJ', 'SYM', 'VERB', 'X'],
                    help=('Avgrensar søket til éi ordklasse, elles inga '
                          'avgrensing. Sjå '
                          'https://universaldependencies.org/u/pos/index.html '
                          'for meir informasjon.'))
parser.add_argument('-i', '--innretningstype',
                    choices=['forklåring', 'døme', 'samansetjingar'],
                    help=('Filtrerer ved innretningstype. Sjå README.md for '
                          'nærmare informasjon.'))
parser.add_argument('-u', '--utputt',
                    help=('Utputtfila. Om ikkje definert vert resultata skrivne '
                          'til stdout.'))


def henta_respons(api_sti, params=None):
    """Kallar REST API-et med requests.get().

    Sidan feila kan vera uføreseilege, fangar try-blokken alt.

    Args:
        api_sti: Streng av stien til API-endepunktet.
        params: Dict, ei liste av tuplar eller bytes for å senda i søkjestrengen
    	  til API-et. (Frå https://docs.python-requests.org/en/latest/api/#requests.get.)

    Returns:
        Ein dict frå requests.Response av JSON-innhaldet i responsen.
    """
    try:
        resp = requests.get(api_sti, params=params)
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    if not resp:
        sys.stderr.write('API-søket har feila:\n{0}\n'.format(resp.content))
        sys.exit(1)

    return resp.json()


@functools.cache
def erstatta_søkjestreng(s):
    """Erstattar søkjestrengen frå Ordbok-API-et med eit regulært uttrykk.

    Args:
    	s: Den opphavelege søkjestrengen.

    Returns:
    	s: Søkjestrengen som regulært uttrykk (str).
    """
    for x, y in [('_*', '.+'), ('*', '.*'), ('%', '.*'), ('_', '.')]:
        s = s.replace(x, y)

    return s


def samanslå_artiklar(alle_artiklane):
    """Slår saman dei to listene av bokmålske og nynorske artikkel-ID-ar.

    Responsen frå API-et skil bokmåls- og nynorskartiklar frå kvarandre, som
    ikkje er nødvendig for dette programmet.

    Args:
    	alle_artiklane: Ein dict av streng til liste, til dømes:

    	  {'bm': [136192, 66170, …], 'nn': [140465, 87000, …]}

    Yields:
    	Ein tuppel av (ordbok, artikkel-ID) t.d. ('bm', 136192).
    """
    for ordbok, artiklar in alle_artiklane.items():
        for artikkel in artiklar:
            yield (ordbok, artikkel)


def henta_artiklar(api_sti, params=None):
    """Kallar REST API-et for å henta lista over artiklar.

    Args:
        api_sti: Streng av stien til API-endepunktet.
        params: Dict, ei liste av tuplar eller bytes for å senda i søkjestrengen
    	  til API-et. (Frå https://docs.python-requests.org/en/latest/api/#requests.get.)

    Yields (from):
        Det same som samanslå_artiklar(), ein tuppel av (ordbok, artikkel-ID).
    """
    resp = henta_respons(api_sti, params=params)
    yield from samanslå_artiklar(resp['articles'])


def henta_innretningar(definisjonar):
    """Rekursivt finn forklårande innretningar.

    «Forklårande innretning» er brukt her om dei ulike slags definisjonar som
    Ordbok-API-et bruker: forklåring, døme, liste av samansette ord og
    delartikkel. Sjå README.md for meir informasjon.

    Args:
    	definisjonar: Ei liste av forklårande innretningar, evt. med fleire
    	  nysta inne i.

    Yields:
    	Ein dict av éi forklårande innretning med metadata om henne.
    """
    for d in definisjonar:

        try:
            if d['type_'] == 'definition':
                yield from henta_innretningar(d['elements'])
        except KeyError as e:
            sys.stderr.write(
                'Det har oppstått ein KeyError. Venlegast opna ein issue hjå '
                'https://github.com/quaepoena/fritekstsoek/issues og gjev att '
                'fylgjande: {}.\n'.format(sys.argv))

        if d['type_'] == 'sub_article':
            yield from henta_innretningar(d['article']['body']['definitions'])
        elif d['type_'] != 'definition':
            yield d


@functools.cache
def henta_konsept(ordbok, nykel):
    """Slår opp forkortingar for å skriva dei ut.

    Args:
    	ordbok (str): Ordboka, anten 'bm' eller 'nn'.
    	nykel (str): Ei forkortning, brukt som nykel i JSON-objektet, som
    	  svarer til eit ord.
    """
    resp = henta_respons('https://ord.uib.no/{0}/concepts.json'.format(ordbok))
    return resp['concepts'][nykel]['expansion']


def erstatta(innhald, erstatningar, ordbok):
    """Erstatta «$»-ar i innhaldet med erstatningane.

    Args:
    	innhald (str): Det opphavelege innhaldet med eventuelle «$»-teikn
    	  som skal erstattast.
    	erstatningar: Ei liste av dict-ar med erstatningsinformasjon.
    	ordbok (str): Ordboka, anten 'bm' eller 'nn'.

    Returns:
    	innhald (str): Strengen med eventuelle «$»-teikn erstatta.
    """
    for e in erstatningar:
        match e['type_']:
            case 'article_ref':
                innhald = innhald.replace('$', e['lemmas'][0]['lemma'], 1)
            case ('domain' | 'entity' | 'grammar' | 'language' | 'relation' |
                  'rhetoric' | 'temporal'):
                innhald = innhald.replace('$', henta_konsept(ordbok, e['id']), 1)
            case 'usage':
                innhald = innhald.replace('$', e['text'], 1)
            case 'superscript' if e['text'] == '2':
                innhald = innhald.replace('$', '²', 1)
            case 'superscript' if e['text'] == '3':
                innhald = innhald.replace('$', '³', 1)

    return innhald


def byggja_innhald(innretning, ordbok):
    """Lagar innhaldet i ei forklårande innretning.

    Args:
    	innretning: Ein dict av ei forklårande innretning med metadata om henne.
    	ordbok (str): Ordboka, anten 'bm' eller 'nn'.

    Returns:
    	innhald (str): Den forklårande teksta som det står i ordboka, men utan
    	  eventuelle lenkjer til ardre artiklar.
    """
    match innretning['type_']:
        case 'compound_list':
            innhald = erstatta(innretning['intro']['content'],
                               innretning['intro']['items'], ordbok)

            innhald += ' '
            innhald += ', '.join([e['lemmas'][0]['lemma']
                                  for e in innretning['elements']])

        case 'example':
            innhald = erstatta(innretning['quote']['content'],
                               innretning['quote']['items'], ordbok)
        case 'explanation':
            innhald = erstatta(innretning['content'],
                               innretning['items'], ordbok)

    return innhald


@functools.cache
def norsk_ordklasse(infl_gr):
    """Gjev att ordklassa på norsk.

    Args:
    	infl_gr (str): Ein streng med ordklasseinformasjon, «inflection
    	  group», på engelsk.

    Returns:
    	ordklasse (str): Ordklassa på norsk, eller 'ukjent' om det ikkje finst her.
    """
    if infl_gr.startswith('ABBR'): ordklasse = 'forkorting'
    elif infl_gr.startswith('ADJ'): ordklasse = 'adjektiv'
    elif infl_gr.startswith('ADP'): ordklasse = 'preposisjon'
    elif infl_gr.startswith('ADV'): ordklasse = 'adverb'
    elif infl_gr.startswith('CCONJ'): ordklasse = 'konjunksjon'
    elif infl_gr.endswith('PFX'): ordklasse = 'prefiks'
    elif infl_gr.startswith('DET'): ordklasse = 'determinativ'
    elif infl_gr.startswith('EXPR'): ordklasse = 'uttrykk'
    elif infl_gr.startswith('INTJ'): ordklasse = 'interjeksjon'
    elif infl_gr.startswith('NOUN'): ordklasse = 'substantiv'
    elif infl_gr.startswith('PRON'): ordklasse = 'pronomen'
    elif infl_gr.startswith('SCONJ'): ordklasse = 'subjunksjon'
    elif infl_gr.startswith('SYM'): ordklasse = 'symbol'
    elif infl_gr.startswith('VERB'): ordklasse = 'verb'
    else: ordklasse = 'ukjent'

    return ordklasse


@functools.cache
def norsk_innretningstype(innretningstype):
    """Omset namn på innretningstype til norsk.

    Sjå README.md for meir informasjon om innretningstypar.

    Args:
    	innretningstype (str): Innretningstypen på engelsk.

    Returns:
    	Ein streng på norsk.
    """
    eng_til_nor = {'compound_list': 'samansetjingar',
                   'example': 'døme',
                   'explanation': 'forklåring'}

    return eng_til_nor[innretningstype]


def henta_artikkelinnhald(api_sti, ordbok, artikkel):
    """Samlar informasjonen om alle innretningstypane i ein artikkel.

    Args:
        api_sti: Streng av stien til API-endepunktet.
    	ordbok (str): Ordboka, anten 'bm' eller 'nn'.
    	artikkel (int): Artikkel-ID-en.

    Yields:
    	Ein dict med éi forklårande innretning og metadata om henne.
    """
    resp = henta_respons(
        '{0}/{1}/article/{2}.json'.format(api_sti, ordbok, artikkel))

    ordklasse = norsk_ordklasse(
        resp['lemmas'][0]['paradigm_info'][0]['inflection_group'])
    lemma = resp['lemmas'][0]['lemma']

    for innretning in henta_innretningar(resp['body']['definitions']):
        yield {'ordbok': ordbok, 'ordklasse': ordklasse,
               'lemma': lemma, 'artikkel_id': artikkel,
               'type': norsk_innretningstype(innretning['type_']),
               'innhald': byggja_innhald(innretning, ordbok)}


def matchar(innhald, søk):
    return re.search(erstatta_søkjestreng(søk), innhald)


def køyra_fritekstsøk(søk, ordbok, api_sti, ordklasse=None):
    """Finn ordboksartiklar som matchar søkjestrengen.

    Args:
    	søk (str): Søkjestrengen.
    	ordbok (str): Ordboka, anten 'bm' eller 'nn'.
        api_sti (str): Streng av stien til API-endepunktet.
    	ordklasse: Streng av ordklassa ein vil leita etter, evt. None om ein
    	  vil sjå alle.

    Yields:
    	Ein dict av ein innretningstype som matchar søkjestrengen med både
    	  søkjestrengjen og all informasjonen henta frå henta_artikkelinnhald().
    """
    params = {'w': søk, 'dict': ordbok, 'wc': ordklasse, 'scope': 'f'}
    artiklar = henta_artiklar('{}/api/articles'.format(api_sti), params=params)

    artikkelinnhald = itertools.chain.from_iterable(
        map(lambda x: henta_artikkelinnhald(api_sti, x[0], x[1]), artiklar))

    match_par = functools.partial(matchar, søk=søk)
    for a in filter(lambda x: match_par(x['innhald']),
                    artikkelinnhald):
        yield a | {'søk': søk}


def skriva_til_fil(resultat, utputtfil, fieldnames):
    """Skriv ut ei CSV-fil."""
    with open(utputtfil, 'w') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        [w.writerow(r) for r in resultat]


def riktig_innretningstype_p(innretning, innretningstype):
    return innretning['type'] == innretningstype


def main(flags):
    resultat = køyra_fritekstsøk(flags.søk, flags.ordbok, flags.api,
                                 ordklasse=flags.ordklasse)

    if flags.innretningstype:
        riktig_inn = functools.partial(riktig_innretningstype_p,
                                       innretningstype=flags.innretningstype)
        resultat = filter(riktig_inn, resultat)

    fieldnames=['søk', 'ordbok', 'ordklasse', 'lemma', 'artikkel_id', 'type', 'innhald']
    if flags.utputt:
        skriva_til_fil(resultat, flags.utputt, fieldnames)
    else:
        w = csv.DictWriter(sys.stdout,
                           fieldnames=fieldnames)
        w.writeheader()
        [w.writerow(r) for r in resultat]


if __name__ == '__main__':
    main(parser.parse_args())
