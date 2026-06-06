import argparse
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


def finna_forkl_inn(definisjonar):
    """Finn lista over forklårande innretningar.

    Ordbok-API-et bruker ordet «definisjonar» på ulike måtar, og difor skil
    dette programmet ut alt som går inn i «éin» definisjon som «forklårande
    innretningar». Til dømes bruker artikkelen til substantivet «liste»,
    https://ordbokene.no/nno/nn/45865, både forklåringar («skriftleg
    opprekning …»), døme («setje opp ei liste») og ei «compound»-liste («som
    etterledd …»). Dette programmet, og dimed denne funksjonen, er berre
    interessert i den fyrste typen, forklåringar.

    Args:
    	definisjonar: Ei liste frå HTTP-responsen som, grovt sagt, svarar til ei
    	  liste av tydingar.

    Returns:
    	forklårande_innretningar: Ei liste av strengar av forklårande tekst.
    """
    forklårande_innretningar = []

    for definisjon in definisjonar:
        if 'elements' in definisjon:
            forklårande_innretningar.extend(filter(is_explanation, definisjon['elements']))
        else:
            forklårande_innretningar.extend(filter(is_explanation, [definisjon]))

    return forklårande_innretningar


def is_article_ref(x):
    """Filtrerer artikkelreferansar."""
    return x['type_'] == 'article_ref'


# TODO: Erstatta alle «$»-ane.
def førebu_innhald(innretning):
    """Erstattar «$» i forklårande tekst.

    Per no finst det andre bruksområde for «$» som ikkje vert erstatta.

    Args:
    	innretning: Ein dict frå HTTP-responsen som inkluderer forklårande
    	  tekst.

    Returns:
    	innhald: Den forklårande teksta med artikkelreferansar erstatta med
    	  det tilsvarande lemmaet.
    """
    innhald = innretning['content']

    for i in filter(is_article_ref, innretning['items']):
        innhald = innhald.replace('$', i['lemmas'][0]['lemma'], 1)

    return innhald


def main(flags):

    for søkjestreng in flags.søk:
        params = {'w': søkjestreng, 'dict': flags.ordbok,
                  'wc': flags.ordklasse, 'scope': 'f'}
        resp_artiklar = henta_respons('{}/api/articles'.format(flags.api), params=params)

        søkje_re = erstatta_søkjestreng(søkjestreng)

        for ordbok, artikkel in samanslå_artiklar(resp_artiklar['articles']):
            resp_artikkel = henta_respons(
                '{0}/{1}/article/{2}.json'.format(flags.api, ordbok, artikkel))

            lemma = resp_artikkel['lemmas'][0]['lemma']
            definisjonar = resp_artikkel['body']['definitions'][0]['elements']
            forklårande_innretningar = finna_forkl_inn(definisjonar)

            for forklårande_innretning in forklårande_innretningar:
                innhald = førebu_innhald(forklårande_innretning)

                if re.search(søkje_re, innhald):
                    print('{0};{1};{2};{3}'.format(søkjestreng, ordbok, lemma, innhald))


if __name__ == '__main__':
    main(parser.parse_args())
