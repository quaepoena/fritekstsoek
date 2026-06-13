# fritekstsøk

Dette programmet bruker Ordbok API-et til å laga CSV-utputt med, blant anna,
lemmaet og definisjonen som matchar i eit fritekstsøk. Ein kan filtrera etter
ordbok, ordklasse og definisjonstype (sjå nedanføre).

## Definisjonstypar

Ordbok API-et bruker ulike definisjonstypar, som er kalla for «forklårande
innretningar» i dette programmet for å skilja dei frå kvarandre. Dei som er
aktuelle, og som brukaren kan filtrera etter, er «forklåring», «døme» og
«samansetjingar». Artikkelen til [«del»](https://ordbokene.no/nno/nn/11243) i
Nynorskordboka viser desse tre:

- forklåring: «avgrensa stykke av ein heilskap»
- døme: «utskiftbare delar»
- samansetjingar: «som etterledd i ord som maskindel reservedel setningsdel»

Merk at ikkje alle samansetjingar i ordbøkene er klassifiserte som
«samansetjingar» (_compound_liste_) i API-et, jf. [«sti
I»](https://ordbokene.no/nno/nn/73682) i Nynorskordboka der «i ord som svinesti»
er klassifisert som «forklåring».

## Søkjestrengar

[Dei tillatne søkjeteikna](https://ordbokene.no/nno/help/advanced) er dei same
som på ordbokene.no.

## Bruksdøme

Eit søk etter alle artiklane som matchar 'svine%':

```
$ python fritekstsøk.py -s svine%
søk,ordbok,ordklasse,lemma,artikkel_id,type,innhald
svine%,bm,substantiv,svor,58822,forklåring,hud på svinekjøtt
svine%,bm,substantiv,villsvin,68366,forklåring,mellomstort dyr i svinefamilie med lange støttenner og stiv pels
svine%,bm,substantiv,gris,20985,forklåring,"husdyr i svinefamilie med tykk kropp, korte bein, små øyne og tryne"
svine%,bm,substantiv,smult,54870,forklåring,smeltet svinefett som brukes til matlaging og såpeproduksjon
svine%,bm,uttrykk,svine til,105648,døme,svine til offentlige toaletter
…
svine%,nn,substantiv,svor,76201,forklåring,hud på svinekjøt
svine%,nn,substantiv,transjering,137846,døme,transjering av svinesteik
svine%,nn,substantiv,villsvin,90015,forklåring,mellomstort dyr i svinefamilie med lange støyttenner og stiv pels
svine%,nn,substantiv,svin,76093,forklåring,klauvdyr i svinefamilie med kraftig kropp og spist hovud med små auge og tryne
svine%,nn,substantiv,svin,76093,forklåring,"husdyr av svinefamilie med tjukk kropp, korte bein, små auge og tryne"
svine%,nn,substantiv,svin,76093,døme,"han slo meg, det svinet"
…
```

Den same søkjestrengen filtrert etter substantiv og definisjonstypen «døme» i
Bokmålsordboka:

```
python fritekstsøk.py -s svine% -o bm -i døme -k NOUN
søk,ordbok,ordklasse,lemma,artikkel_id,type,innhald
svine%,bm,substantiv,svin,58747,døme,"han slo meg ned, det svinet"
svine%,bm,substantiv,svinekam,118905,døme,servere svinekam med soppsaus
svine%,bm,substantiv,svinesti,58775,døme,festlokalet så ut som en svinesti
svine%,bm,substantiv,svinesti,58775,døme,de har gjort området til en svinesti
svine%,bm,substantiv,svineri,58773,døme,gulvet fløt av oppkast og annet svineri
…
```

Om ein vil samanlikna bruken av `svin%` vs. `gris%` med verb i ordbøkene:

```
python fritekstsøk.py -s 'svin%|gris%' -k VERB
søk,ordbok,ordklasse,lemma,artikkel_id,type,innhald
svin%,bm,verb,styrte,58022,døme,svindleren styrtet dem alle i ulykken
svin%,bm,verb,curle,108693,forklåring,"rotere, svinge, skru"
svin%,bm,verb,svive,58816,døme,bilen sveiv i svingen
…
gris%,bm,verb,velte,67535,døme,grisen veltet seg i gjørma
gris%,bm,verb,ete,13208,døme,grisene eter seg opp til slaktevekt
gris%,bm,verb,rote,48931,døme,grisen roter i jorda
…
svin%,nn,verb,styrte,74902,døme,svindlaren styrta dei alle i ulykka
svin%,nn,verb,lure,46855,døme,vi lot oss lure av svindlarar
svin%,nn,verb,svive,76181,døme,bilen sveiv i svingen
…
gris%,nn,verb,velte,88640,døme,grisen velte seg i gjørma
gris%,nn,verb,ete,15798,døme,grisane et seg opp til slaktevekt
gris%,nn,verb,utarte,85800,døme,sparinga kan utarte til griskleik
…
```

## N.B.

- Berre det fyrste lemmaet er vist i eit resultat. Til dømes om eit søk matchar
artikkelen [«rekkjefylgje»](https://ordbokene.no/nno/nn/61030), vert lemmaet
vist som «rekkjefølgje».

- Ordbok-API-et bruker omgrepet «underartikkel» (_sub_article_) for faste
uttrykk, jf. «sitje att» under [«sitja»](https://ordbokene.no/nno/nn/66054). Om
teksta i ein underartikkel matchar søkjestrengen, vert ikkje namnet på
underartikkelen («sitje att») vist som lemmaet i resultatet, heller hovudlemmaet
(«sitje»).

## Avhengnader

Programmet krev Python 3.9 eller seinare på grunn av `|`-operatoren brukt med
ein dict. Bibloteket `requests` er brukt, som ligg utanføre standardbiblioteket.
