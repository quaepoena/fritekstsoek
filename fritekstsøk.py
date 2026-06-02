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
parser.add_argument('-o', '--ordbok', required=True, type=str,
                    choices=['bm', 'nn', 'bm,nn'], default='bm,nn',
                    help='Ordbok/-bøkene som skal brukast. Default er båe to.')
parser.add_argument('--api', default='https://ord.uib.no',
                    help='API-et som skal brukast.')


def henta_respons(api_sti, params=None):
    try:
        resp = requests.get(api_sti, params=params)
    except e:
        sys.stderr.write(e)
        sys.exit(1)

    if not resp:
        sys.stderr.write('API-søket har feila:\n{0}\n'.format(resp.content))
        sys.exit(1)

    return resp.json()


# Erstatta søkjestrengen med eit regulært uttrykk.
def erstatta_søkjestreng(s):
    for x, y in [('_*', '.+'), ('*', '.*'), ('%', '.*'), ('_', '.')]:
        s = s.replace(x, y)

    return s


def samanslå_ordbok_og_artiklar(alle_artiklane):
    ordbok_og_artiklar = []

    for ordbok, artiklar in alle_artiklane.items():
        for artikkel in artiklar:
            ordbok_og_artiklar.append((ordbok, artikkel))

    return ordbok_og_artiklar


def is_explanation(x):
    return x['type_'] == 'explanation'


def finna_forkl_inn(definisjonar):
    forklårande_innretningar = []

    for definisjon in definisjonar:
        if 'elements' in definisjon:
            forklårande_innretningar.extend(filter(is_explanation, definisjon['elements']))
        else:
            forklårande_innretningar.extend(filter(is_explanation, [definisjon]))

    return forklårande_innretningar


def is_article_ref(x):
    return x['type_'] == 'article_ref'


def førebu_innhald(innretning):
    innhald = innretning['content']

    for i in filter(is_article_ref, innretning['items']):
        innhald = innhald.replace('$', i['lemmas'][0]['lemma'], 1)

    return innhald


def main(flags):

    for søkjestreng in flags.søk:
        params = {'w': søkjestreng, 'dict': flags.ordbok, 'wc': 'NOUN', 'scope': 'f'}
        resp_artiklar = henta_respons('{}/api/articles'.format(flags.api), params=params)

        søkjestreng = erstatta_søkjestreng(søkjestreng)
        ordbok_og_artiklar = samanslå_ordbok_og_artiklar(resp_artiklar['articles'])

        for ordbok, artikkel in ordbok_og_artiklar:
            resp_artikkel = henta_respons(
                '{0}/{1}/article/{2}.json'.format(flags.api, ordbok, artikkel))

            lemma = resp_artikkel['lemmas'][0]['lemma']
            definisjonar = resp_artikkel['body']['definitions'][0]['elements']
            forklårande_innretningar = finna_forkl_inn(definisjonar)

            for forklårande_innretning in forklårande_innretningar:
                innhald = førebu_innhald(forklårande_innretning)

                if re.search(søkjestreng, innhald):
                    print('{0};{1};{2};{3}'.format(søkjestreng, ordbok, lemma, innhald))


if __name__ == '__main__':
    main(parser.parse_args())
