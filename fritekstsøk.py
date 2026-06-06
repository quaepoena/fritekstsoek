import argparse
import csv
import functools
import operator
import re
import requests
import sys


def parse_string(x):
    return x.split()


parser = argparse.ArgumentParser(
    description=('Visa leksem med og definisjonar som matchar eit fritekstsøk. '
                 'Bruker Ordbok API: https://ord.uib.no/ord_2_API.html\n \n'
                 'Brukseksempel:\n \n'
                 'python fritekstsøk.py -s \'stor liten\' \' --ordbok'),
    formatter_class=argparse.RawTextHelpFormatter,
    prog='fritekstsøk')
parser.add_argument('-s', '--søk', required=True, type=parse_string,
                    help='Ein søkjestreng, evt. søkjestrengar skilde med mellomrom.')
parser.add_argument('-o', '--ordbok', type=str, choices=['bm', 'nn', 'bm,nn'],
                    default='bm,nn',
                    help='Ordbok/-bøkene som skal brukast. Default er båe to.')
parser.add_argument('--api', default='https://ord.uib.no',
                    help='API-et som skal brukast.')
parser.add_argument('--ordklasse',
                    choices=['ADJ', 'ADP', 'ADV', 'CCONJ', 'DET', 'INTJ',
                             'NOUN', 'NUM', 'PART', 'PRON', 'PROPN', 'PUNCT',
                             'SCONJ', 'SYM', 'VERB'],
                    help=('Avgrensar søket til éi ordklasse. Eit utval frå '
                          'https://universaldependencies.org/u/pos/index.html.'))
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
    except e:
        sys.stderr.write(e)
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

    Responsen frå API-et skil bokmåls- og nynorskartiklar frå kvarandre. For å
    redusera kompleksiteten i main() vert dei slegne saman til éi liste.

    Args:
    	alle_artiklane: Ein dict av streng til liste, til dømes:

    	  {'bm': [136192, 66170, …], 'nn': [140465, 87000, …]}

    Yields:
    	Ein tuppel av (ordbok, artikkel-ID) t.d. ('bm', 136192).
    """
    for ordbok, artiklar in alle_artiklane.items():
        for artikkel in artiklar:
            yield (ordbok, artikkel)


def is_explanation(x):
    """Filtrerer forklårande tekst."""
    return x['type_'] == 'explanation'


@functools.cache
def henta_konsept(ordbok, nykel):
    r = requests.get('https://ord.uib.no/{0}/concepts.json'.format(ordbok))
    return r.json()['concepts'][nykel]['expansion']


def førebu_innhald(innretning, *, ordbok=None):
    """Erstattar «$» i forklårande tekst.

    Per no finst det andre bruksområde for «$» som ikkje vert erstatta.

    Args:
    	innretning: Ein dict med éi forklårande innretning og metadata om henne.
    	ordbok (str): Ordboka ordet finst i.

    Returns:
    	innhald (str): Den forklårande teksta med artikkelreferansar erstatta
    	  med det tilsvarande lemmaet.
    """
    innhald = innretning['content']

    for item in innretning['items']:

        match item['type_']:
            case 'article_ref':
                innhald = innhald.replace('$', item['lemmas'][0]['lemma'], 1)
            case ('domain' | 'entity' | 'grammar' | 'language' | 'relation' |
                  'rhetoric' | 'temporal'):
                innhald = innhald.replace(
                    '$', henta_konsept(ordbok, item['id']), 1)
            case 'usage':
                innhald = innhald.replace('$', item['text'], 1)

    return innhald


def henta_artiklar(api_sti, params=None):
    """Kallar REST API-et med requests.get().

    Sidan feila kan vera uføreseilege, fangar try-blokken alt.

    Args:
        api_sti: Streng av stien til API-endepunktet.
        params: Dict, ei liste av tuplar eller bytes for å senda i søkjestrengen
    	  til API-et. (Frå https://docs.python-requests.org/en/latest/api/#requests.get.)

    Returns:
        Generatoren frå samanslå_artiklar().
    """
    resp = henta_respons(api_sti, params=params)
    return samanslå_artiklar(resp['articles'])


def finna_innretningar(resp):
    """Finn lista over forklårande innretningar.

    «Forklårande innretning» er brukt her om dei ulike slags definisjonar som
    Ordbok-API-et bruker: forklåring, døme og liste av samansette ord med
    leksemet som etterledd. (Det finst kanskje fleire.) Denne funksjonen finn
    alle slike innretningar, som då vert filtrerte etter kvart til berre
    «vanlege» forklåringar.

    Strukturen til polyseme ord er forskjellig frå den til monoseme, og difor er
    det naudsynleg å testa om ordet er polysemt, og so bruka ei for-blokk til om
    det er.

    Args:
    	resp (dict): Ein ordbokartikkel som JSON frå
    	  requests.Reponse.json().

    Yields:
    	Ein dict med éi forklårande innretning og metadata om henne.

    """
    definisjonar = resp['body']['definitions'][0]['elements']

    for definisjon in definisjonar:
        if 'elements' in definisjon:
            for element in definisjon['elements']:
                yield element
        else:
            yield definisjon


@functools.cache
def henta_ordklasse(infl_gr):
    """Gjev att ordklassa på norsk.

    Args:
    	infl_gr (str): Ein streng med ordklasseinformasjon, «inflection
    	  group», på engelsk.

    Returns:
    	ordklasse (str): Ein streng på norsk som tilsvarer det ein ser i
    	  ordbøkene på nett.
    """
    ordklasse = ""
    if infl_gr.startswith('VERB'): ordklasse = 'verb'
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
    else: ordklasse = 'ukjent'

    return ordklasse


def finna_forklåringar(ordbok, artikkel, api_sti=None):
    """Finn forklåringane i ein ordbokartikkel.

    Args:
    	ordbok (str): Ordboka, anten 'bm' eller 'nn'.
    	artikkel (int): Artikkel-ID-en.
        api_sti: Streng av stien til API-endepunktet.

    Returns:
    	Ei liste av dict-ar med ei forklåring og informasjon om
    	  lemmaet og ordboka.
    """
    resp = henta_respons(
        '{0}/{1}/article/{2}.json'.format(api_sti, ordbok, artikkel))

    forklåringar = filter(is_explanation, finna_innretningar(resp))
    førebu = functools.partial(førebu_innhald, ordbok=ordbok)
    forklåringar = map(førebu, forklåringar)

    lemma = resp['lemmas'][0]['lemma']
    infl_gr = resp['lemmas'][0]['paradigm_info'][0]['inflection_group']
    ordklasse = henta_ordklasse(infl_gr)

    return [{'lemma': lemma, 'ordbok': ordbok, 'forklåring': forklåring,
             'ordklasse': ordklasse}
            for forklåring in forklåringar]


def køyra_fritekstsøk(søk, ordbok, api_sti, ordklasse=None):
    """Finn ordboksartiklar som matchar søkjestrengen.

    Args:
    	søk (str): Søkjestrengen.
    	ordbok (str): Ordboka, anten 'bm' eller 'nn'.
        api_sti (str): Streng av stien til API-endepunktet.
    	ordklasse: Streng av ordklassa ein vil leita etter, evt. None om ein
    	  vil sjå alle.

    Returns:
    	Ei liste av dict-ar der kvar dict er eit matchande resultat saman med
    	  søkjestrengen, ordboka, ordklassa og lemmaet.
    """
    params = {'w': søk, 'dict': ordbok, 'wc': ordklasse, 'scope': 'f'}
    artiklar = henta_artiklar('{}/api/articles'.format(api_sti), params=params)

    finna_forkl = functools.partial(finna_forklåringar, api_sti=api_sti)
    forklåringar = map(lambda x: finna_forkl(x[0], x[1]), artiklar)
    forklåringar = functools.reduce(operator.concat, forklåringar)

    matchande = filter(lambda x: re.search(erstatta_søkjestreng(søk), x['forklåring']),
                       forklåringar)

    return [m | {'søk': søk} for m in matchande]


def skriva_ut(resultat, utputtfil=None, *, fieldnames=None):
    """Skriv ut som CSV."""
    with open(utputtfil, 'w') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        [w.writerow(r) for r in resultat]


def main(flags):
    køyra = functools.partial(køyra_fritekstsøk, ordbok=flags.ordbok,
                              api_sti=flags.api, ordklasse=flags.ordklasse)
    resultat = functools.reduce(operator.concat, map(køyra, flags.søk))

    fieldnames=['søk', 'ordbok', 'lemma', 'ordklasse', 'forklåring']
    if flags.utputt:
        skriva_ut(resultat, flags.utputt, fieldnames=fieldnaems)
    else:
        w = csv.DictWriter(sys.stdout,
                           fieldnames=fieldnames)
        w.writeheader()
        [w.writerow(r) for r in resultat]


if __name__ == '__main__':
    main(parser.parse_args())
