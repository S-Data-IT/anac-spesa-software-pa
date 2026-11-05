# Analisi open data ANAC: spesa PA in software e servizi IT (CPV 72*)

Statistiche aggregate sugli **importi di aggiudicazione** dei contratti pubblici italiani con codice CPV che inizia per `72` (servizi informatici), CIG pubblicati nel **2024** e nel **2025**. Fonte: open data [ANAC](https://dati.anticorruzione.it/opendata). Scarico dei file: **27 ottobre 2026**.

- Pagina (quando online): <https://www.s-data.it/spesa-pa-software-anac.html>
- Homepage S-Data: <https://www.s-data.it>
- CSV aggregato (solo n / quartili / mediana): [`anac-cpv72-aggiudicazioni-2024-2025.csv`](anac-cpv72-aggiudicazioni-2024-2025.csv)
- Script riproducibile: [`anac_cpv72.py`](anac_cpv72.py) (solo libreria standard Python 3)
- Licenza di questo dataset derivato: [CC BY-SA 4.0](LICENSE)

**Non è un listino né un prezzo di mercato del software gestionale su misura per PMI.** Il committente è la Pubblica Amministrazione; i contratti CPV 72* includono anche manutenzione, assistenza, canoni, hosting, formazione, adesioni a convenzioni e progetti PNRR. Vedi i limiti sotto.

## Risultati in breve (importi in €, come pubblicati da ANAC)

| Gruppo | Anno | n | Q1 | Mediana | Q3 |
|---|---|---:|---:|---:|---:|
| CPV 72* totale | 2024 | 34.765 | 8.150 | 16.458 | 41.000 |
| CPV 72* totale | 2025 | 64.105 | 7.721 | 15.000 | 37.200 |
| 72212 – sviluppo software applicativi | 2024 | 1.764 | 8.200 | 17.175 | 41.618 |
| 72212 | 2025 | 3.261 | 8.125 | 16.452 | 39.080 |
| 72262 – sviluppo di software | 2024 | 264 | 13.675 | 39.775 | 165.857 |
| 72262 | 2025 | 601 | 11.700 | 36.000 | 130.000 |
| 72267 – manutenzione software | 2024 | 3.324 | 8.100 | 14.820 | 31.500 |
| 72267 | 2025 | 6.306 | 8.197 | 15.000 | 32.636 |
| Sottoinsieme conservativo (filtro nostro) | 2024 | 659 | 9.900 | 19.500 | 46.925 |
| Sottoinsieme conservativo | 2025 | 1.154 | 9.919 | 19.420 | 39.900 |

Il CSV include anche P10/P90 e il gruppo 72260–72268. **Non pubblichiamo il 2023** come confronto: dal 2024 (digitalizzazione dei contratti pubblici) i file non sono omogenei con il 2023 (mediana 2023 ≈ 33.000 € vs 15–16.000 € nel 2024–25: cambio di regime di comunicazione, non necessariamente di prezzi).

## Fonti

Portale: <https://dati.anticorruzione.it/opendata> — Autorità Nazionale Anticorruzione (ANAC).

| Dataset | Contenuto usato |
|---|---|
| CIG 2023, 2024, 2025 (file mensili `cig_csv_AAAA_MM.zip`) | `cod_cpv`, `importo_lotto`, procedura, oggetto, stazione appaltante, `FLAG_PNRR_PNC`, anno/mese pubblicazione |
| Aggiudicazioni (base + aggiornamenti) | `importo_aggiudicazione`, `esito`, date |

Pagine dataset: [aggiudicazioni](https://dati.anticorruzione.it/opendata/dataset/aggiudicazioni) · [CIG 2025](https://dati.anticorruzione.it/opendata/dataset/cig-2025) (idem 2024, 2023).

Nota tecnica: il portale respinge richieste senza User-Agent da browser; lo script ne invia uno.

## Metodo

1. Dai CIG 2023–2025 si tengono le righe con `cod_cpv` che inizia per `72` (150.847 righe, 149.427 CIG).
2. Per ogni CIG si usa il CPV con `flag_prevalente`=1 (se assente, la prima riga).
3. Join su `cig` con le aggiudicazioni: esito `AGGIUDICATA` e `importo_aggiudicazione` > 0; con più righe vale la più recente (file di aggiornamento batte la base). Risultato: **113.991** CIG con importo utilizzabile.
4. Statistiche (n, Q1, mediana, Q3, P10, P90; percentile con interpolazione lineare) per sottogruppo CPV e per anno di pubblicazione del CIG.
5. Sottoinsieme «conservativo» (**filtro nostro, soggettivo**): affidamento diretto puro, importo ≤ 140.000 €, oggetto con parole di sviluppo (SVILUPP / REALIZZAZIONE / IMPLEMENTAZIONE / EVOLUTIV) e di software (SOFTWARE / APPLICATIV / PORTALE / GESTIONALE / PIATTAFORMA / WEB / SISTEMA INFORMATIVO), senza MANUTENZ / ASSISTENZA / CANONE / LICENZ / HOSTING / CLOUD / SAAS / ADESIONE / CONVENZIONE / ACCORDO QUADRO / PNRR / FORMAZIONE / HARDWARE / NOLEGG / RINNOVO / «GESTIONE E».

Riproduzione:

```bash
python3 anac_cpv72.py all   # ≈10 minuti, ≈1,5 GB di traffico; scrive data/ e out/
```

Non commitare i CSV grezzi in `data/` né `out/contratti_cpv72_aggiudicati.csv` (decine di MB). Pubblicabile solo il CSV aggregato di questa cartella.

## Limiti (da leggere prima di citare)

- **Affidabile** come descrizione di ciò che è nei dati ANAC (riproducibile con lo script e gli stessi file).
- **Non affidabile** come prezzo di mercato del software gestionale su misura per PMI private.
- **PA ≠ PMI privata:** procedure, requisiti e prezzi diversi; IVA: non verificato dal tracciato se gli importi siano IVA esclusa.
- **CPV 72* ≠ «software su misura»:** include assistenza, manutenzione, canoni, hosting, formazione, adesioni, PNRR (migliaia di contratti con flag PNRR nel 2024–25).
- **Contratti pluriennali:** l’importo è il totale del contratto, non annuo.
- **Copertura:** circa il 23% dei CIG CPV 72* non ha aggiudicazione nei file (esclusi). Importi probabilmente errati (centinaia sotto i 500 €) non rimossi; molti importi tondi tipici di affidamenti diretti.
- Il sottoinsieme conservativo dipende da parole chiave scelte da noi: cambiando l’elenco cambiano i numeri.
- ANAC **non ha rivisto né avallato** questa elaborazione.

## Licenza e attribuzione

Le risorse ANAC indicano **Creative Commons Attribuzione – Condividi allo stesso modo 4.0 (CC BY-SA 4.0)** (es. risorse CIG 2025). Il registro Open Contracting per il dataset OCDS indica invece CC BY 4.0: **le due indicazioni non coincidono**. Si applica la più restrittiva.

Questo repository (script, CSV aggregato, README) è rilasciato **CC BY-SA 4.0**:

- Attribuzione ad **ANAC** per i dati di origine e a **S-Data** per selezione, join, filtri e statistiche.
- Derivati devono restare CC BY-SA 4.0 e indicare le modifiche.

Formula consigliata:

> S-Data, «Spesa PA in software: analisi open data ANAC (CPV 72*, CIG 2024–2025)», scarico 27 ottobre 2026. https://www.s-data.it/spesa-pa-software-anac.html. Dati di origine: ANAC, dati.anticorruzione.it. Licenza CC BY-SA 4.0.

## Autore

[S-Data](https://www.s-data.it) di Braga Simone, software house dal 2007: software gestionale su misura, web app e integrazioni. Contatto: info@s-data.it · +39 031 366 2851.

Conflitto di interessi dichiarato: S-Data vende servizi di sviluppo software; i numeri ANAC **non** sono usati come listino S-Data e non vanno confrontati direttamente con i prezzi per PMI.
