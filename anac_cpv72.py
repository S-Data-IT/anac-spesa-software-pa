#!/usr/bin/env python3
"""
Analisi open data ANAC: importi di aggiudicazione dei contratti con CPV 72* (servizi IT).

Fonti (ANAC, https://dati.anticorruzione.it/opendata, licenza CC BY-SA 4.0 indicata sulle risorse):
  - dataset "cig-2023", "cig-2024", "cig-2025": file mensili cig_csv_AAAA_MM.zip
    (contengono cod_cpv, importo_lotto, tipo di procedura, stazione appaltante, ESITO)
  - dataset "aggiudicazioni": aggiudicazioni_csv.zip (base, 15/01/2026) + file di aggiornamento
    AAAAMM01-aggiudicazioni_csv.zip (importo_aggiudicazione)
Il join e' sulla colonna `cig`.

Uso:
  python3 anac_cpv72.py fetch     # scarica in streaming, filtra CPV 72*, scarta gli zip (scrive data/)
  python3 anac_cpv72.py analyze   # calcola le statistiche e scrive out/
  python3 anac_cpv72.py all

Solo libreria standard. Dipendenze: nessuna.
"""
import csv, io, os, sys, zipfile, tempfile, urllib.request, statistics, json, re, collections, datetime

BASE = "https://dati.anticorruzione.it/opendata/download/dataset"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
YEARS = [2023, 2024, 2025]
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "out")
csv.field_size_limit(10**9)

AGG_URLS = [f"{BASE}/aggiudicazioni/filesystem/aggiudicazioni_csv.zip"] + [
    f"{BASE}/aggiudicazioni/filesystem/2026{m:02d}01-aggiudicazioni_csv.zip" for m in range(4, 11)]

CIG_KEEP = ["cig", "oggetto_lotto", "importo_lotto", "importo_complessivo_gara", "n_lotti_componenti",
            "oggetto_principale_contratto", "stato", "settore", "cod_tipo_scelta_contraente",
            "tipo_scelta_contraente", "data_pubblicazione", "anno_pubblicazione", "mese_pubblicazione",
            "cod_cpv", "descrizione_cpv", "flag_prevalente", "cf_amministrazione_appaltante",
            "denominazione_amministrazione_appaltante", "provincia", "ESITO", "COD_ESITO", "FLAG_PNRR_PNC", "DURATA_PREVISTA"]
AGG_KEEP = ["cig", "esito", "cod_esito", "importo_aggiudicazione", "data_aggiudicazione_definitiva",
            "data_comunicazione_esito", "id_aggiudicazione", "criterio_aggiudicazione", "ribasso_aggiudicazione"]


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)


def iter_zip_csv(url):
    """scarica lo zip in un file temporaneo, ne legge il CSV in streaming, poi cancella lo zip"""
    with tempfile.TemporaryDirectory() as td:
        z = os.path.join(td, "x.zip")
        download(url, z)
        with zipfile.ZipFile(z) as zf:
            name = zf.namelist()[0]
            with zf.open(name) as raw:
                txt = io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
                for row in csv.DictReader(txt, delimiter=";"):
                    yield row


def fetch():
    os.makedirs(DATA, exist_ok=True)
    # 1) CIG: righe con CPV 72*
    cigs = set()
    with open(os.path.join(DATA, "cig_cpv72.csv"), "w", newline="", encoding="utf-8") as fo:
        w = csv.DictWriter(fo, fieldnames=CIG_KEEP, extrasaction="ignore")
        w.writeheader()
        for y in YEARS:
            for m in range(1, 13):
                url = f"{BASE}/cig-{y}/filesystem/cig_csv_{y}_{m:02d}.zip"
                n = k = 0
                for row in iter_zip_csv(url):
                    n += 1
                    if (row.get("cod_cpv") or "").startswith("72"):
                        w.writerow(row); cigs.add(row["cig"]); k += 1
                print(f"{y}-{m:02d}: {n} righe, {k} con CPV 72*", flush=True)
    print("CIG distinti con CPV 72*:", len(cigs), flush=True)
    # 2) aggiudicazioni dei soli CIG selezionati
    with open(os.path.join(DATA, "agg_cpv72.csv"), "w", newline="", encoding="utf-8") as fo:
        w = csv.DictWriter(fo, fieldnames=AGG_KEEP + ["_fonte"], extrasaction="ignore")
        w.writeheader()
        for url in AGG_URLS:
            n = k = 0
            for row in iter_zip_csv(url):
                n += 1
                if row.get("cig") in cigs:
                    row["_fonte"] = url.rsplit("/", 1)[1]; w.writerow(row); k += 1
            print(f"{url.rsplit('/',1)[1]}: {n} righe, {k} utili", flush=True)
    with open(os.path.join(DATA, "FETCH_INFO.json"), "w") as f:
        json.dump({"data_download": datetime.date.today().isoformat(), "cig_distinti_cpv72": len(cigs),
                   "agg_urls": AGG_URLS}, f, indent=1)


def pct(vals, q):
    """percentile con interpolazione lineare (metodo 7, come numpy default)"""
    s = sorted(vals); n = len(s)
    if n == 1: return s[0]
    p = (n - 1) * q; lo = int(p); hi = min(lo + 1, n - 1)
    return s[lo] + (s[hi] - s[lo]) * (p - lo)


def stats(vals):
    if not vals:
        return dict(n=0)
    return dict(n=len(vals), q1=round(pct(vals, .25)), mediana=round(pct(vals, .5)), q3=round(pct(vals, .75)),
                p10=round(pct(vals, .10)), p90=round(pct(vals, .90)), min=round(min(vals)), max=round(max(vals)))


def f(x):
    try: return float(x)
    except Exception: return None


def load_joined():
    cig = collections.defaultdict(list)
    with open(os.path.join(DATA, "cig_cpv72.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh): cig[r["cig"]].append(r)
    agg = collections.defaultdict(list)
    with open(os.path.join(DATA, "agg_cpv72.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh): agg[r["cig"]].append(r)
    return cig, agg


def analyze():
    os.makedirs(OUT, exist_ok=True)
    cig, agg = load_joined()
    recs = []; scartati = collections.Counter()
    for c, rows in cig.items():
        # CPV prevalente se disponibile, altrimenti la prima riga 72*
        prev = [r for r in rows if r["flag_prevalente"] in ("1", "1.0")] or rows
        r = prev[0]
        if r["cod_cpv"][:2] != "72":
            scartati["CPV prevalente non 72"] += 1; continue
        ags = agg.get(c, [])
        # tengo le aggiudicazioni con esito AGGIUDICATA e importo > 0; se piu' di una, ultima per data comunicazione,
        # a parita' id_aggiudicazione piu' alto (i file di aggiornamento hanno precedenza sul file base)
        ok = [a for a in ags if (a["esito"] or "").strip().upper() == "AGGIUDICATA" and (f(a["importo_aggiudicazione"]) or 0) > 0]
        if not ags: scartati["nessuna aggiudicazione nei file"] += 1; continue
        if not ok: scartati["nessuna aggiudicazione con esito AGGIUDICATA e importo>0"] += 1; continue
        ok.sort(key=lambda a: (a["_fonte"] != "aggiudicazioni_csv.zip", a["_fonte"], a["data_comunicazione_esito"] or "", abs(int(a["id_aggiudicazione"] or 0))))
        a = ok[-1]
        imp = f(a["importo_aggiudicazione"])
        recs.append(dict(cig=c, anno=int(r["anno_pubblicazione"]), cpv=r["cod_cpv"], cpv5=r["cod_cpv"][:5], cpv3=r["cod_cpv"][:3],
                         importo=imp, importo_lotto=f(r["importo_lotto"]), procedura=r["tipo_scelta_contraente"],
                         sa=r["denominazione_amministrazione_appaltante"], oggetto=r["oggetto_lotto"], n_ag_righe=len(ok),
                         n_lotti=r["n_lotti_componenti"], pnrr=r["FLAG_PNRR_PNC"], mese=int(r["mese_pubblicazione"] or 0)))
    print("CIG con CPV 72*:", len(cig), "| con importo aggiudicato utilizzabile:", len(recs))
    for k, v in scartati.items(): print("  scartati:", k, v)

    # qualita': aggiudicazioni multiple, importo > base d'asta, outlier
    multi = sum(1 for x in recs if x["n_ag_righe"] > 1)
    sopra = sum(1 for x in recs if x["importo_lotto"] and x["importo"] > x["importo_lotto"] * 1.001)
    print("CIG con piu' righe aggiudicazione valide:", multi, "| importo aggiudicato > importo lotto:", sopra)

    # sottogruppi
    def sub(name, fn):
        out = {}
        for y in YEARS + ["2023-2025"]:
            vals = [x["importo"] for x in recs if fn(x) and (y == "2023-2025" or x["anno"] == y)]
            out[str(y)] = stats(vals)
        return name, out
    groups = [
        sub("CPV 72* totale", lambda x: True),
        sub("72212 – servizi di sviluppo di software applicativi", lambda x: x["cpv5"] == "72212"),
        sub("72260-72268 – servizi connessi al software (sviluppo, assistenza, manutenzione, ...)", lambda x: x["cpv5"] in ("72260", "72261", "72262", "72263", "72264", "72265", "72266", "72267", "72268")),
        sub("72262 – servizi di sviluppo di software", lambda x: x["cpv5"] == "72262"),
        sub("72267 – servizi di manutenzione e riparazione di software", lambda x: x["cpv5"] == "72267"),
        sub("72310-72322 – servizi di elaborazione dati", lambda x: x["cpv3"] == "723"),
        sub("72500-72611 – servizi informatici, gestione e supporto", lambda x: x["cpv5"] in ("72500", "72510", "72540", "72590", "72600", "72610", "72611")),
        sub("72 – altri sottogruppi", lambda x: x["cpv5"] not in ("72212", "72260", "72261", "72262", "72263", "72264", "72265", "72266", "72267", "72268") and x["cpv3"] != "723"),
    ]
    # distribuzione per sottogruppo CPV a 5 cifre (tutto il periodo)
    by5 = collections.defaultdict(list)
    for x in recs: by5[x["cpv5"]].append(x["importo"])
    by5s = {k: stats(v) for k, v in sorted(by5.items(), key=lambda kv: -len(kv[1]))}
    # fasce di importo (utili a leggere la distribuzione)
    bins = [(0, 5000), (5000, 20000), (20000, 40000), (40000, 100000), (100000, 215000), (215000, 10**12)]
    fasce = {}
    for lo, hi in bins:
        fasce[f"{lo}-{hi}"] = sum(1 for x in recs if lo < x["importo"] <= hi) if lo else sum(1 for x in recs if x["importo"] <= hi)
    # procedure
    proc = collections.Counter(x["procedura"] for x in recs)
    # importi tondi (possibili importi "a base" dichiarati)

    # --- sottoinsieme conservativo "sviluppo software su commessa" (filtro SUGGERITO da noi, soggettivo) ---
    INCL = re.compile(r"SVILUPP|REALIZZAZIONE|PROGETTAZIONE E REALIZZ|IMPLEMENTAZIONE|EVOLUTIV", re.I)
    SW = re.compile(r"SOFTWARE|APPLICATIV|\bAPP\b|PORTALE|GESTIONALE|PIATTAFORMA|WEB|SISTEMA INFORMATIVO", re.I)
    ESCL = re.compile(r"MANUTENZ|ASSISTENZA|CANON|LICENZ|HOSTING|CLOUD|SAAS|ADESIONE|CONVENZIONE|ACCORDO QUADRO|PNRR|FORMAZIONE|HARDWARE|NOLEGG|RINNOVO|GESTIONE E", re.I)
    def cons(x):
        return (INCL.search(x["oggetto"] or "") and SW.search(x["oggetto"] or "") and not ESCL.search(x["oggetto"] or "")
                and x["procedura"] == "AFFIDAMENTO DIRETTO" and x["pnrr"] not in ("1", "1.0") and x["importo"] <= 140000)
    cons_stats = {}
    for y in ("2024", "2025", "2024-2025"):
        vals = [x["importo"] for x in recs if cons(x) and x["anno"] >= 2024 and (y == "2024-2025" or x["anno"] == int(y))]
        cons_stats[y] = stats(vals)
    print("\nSottoinsieme conservativo (affidamento diretto, <=140.000 €, parole chiave sviluppo+software, esclusi manutenzione/PNRR/adesioni):")
    for y, s_ in cons_stats.items(): print(" ", y, s_)
    # sensibilita': tutto CPV 72* ma solo affidamenti diretti <=140k non PNRR, 2024-2025
    base = [x["importo"] for x in recs if x["anno"] >= 2024 and x["procedura"] == "AFFIDAMENTO DIRETTO" and x["importo"] <= 140000 and x["pnrr"] not in ("1", "1.0")]
    print("CPV 72* tutto, affidamenti diretti <=140k non PNRR, 2024-25:", stats(base))
    # importi 'standard' (multipli tondi tipici, es. 5.000, 10.000...) per segnalare concentrazione
    from collections import Counter as C_
    top = C_(round(x["importo"]) for x in recs if x["anno"] >= 2024).most_common(6)
    print("Importi piu' frequenti 2024-25:", top)
    # copertura (CIG con aggiudicazione trovata) per anno
    out_extra = dict(conservativo=cons_stats, base_ad_140k=stats(base), importi_frequenti=top)
    out = dict(**out_extra, data_analisi=datetime.date.today().isoformat(), n_cig_cpv72=len(cig), n_con_importo=len(recs),
               scartati=scartati, multi=multi, sopra_base=sopra, gruppi=dict(groups), per_cpv5=by5s, fasce_importo=fasce,
               procedure=proc.most_common(8))
    with open(os.path.join(OUT, "risultati.json"), "w", encoding="utf-8") as fo:
        json.dump(out, fo, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "contratti_cpv72_aggiudicati.csv"), "w", newline="", encoding="utf-8") as fo:
        w = csv.DictWriter(fo, fieldnames=list(recs[0].keys())); w.writeheader(); w.writerows(recs)
    # CSV aggregato pubblicabile (solo statistiche, nessun dato per singolo contratto): 2024 e 2025
    # Licenza dei dati di origine: CC BY-SA 4.0 -> anche questo derivato va condiviso con CC BY-SA 4.0
    with open(os.path.join(OUT, "anac-cpv72-aggiudicazioni-2024-2025.csv"), "w", newline="", encoding="utf-8") as fo:
        w = csv.writer(fo)
        w.writerow(["gruppo", "anno_pubblicazione_cig", "n_contratti", "q1_eur", "mediana_eur", "q3_eur", "p10_eur", "p90_eur"])
        for name, o in groups[:5]:
            for y in ("2024", "2025"):
                s_ = o[y]
                if s_["n"]: w.writerow([name, y, s_["n"], s_["q1"], s_["mediana"], s_["q3"], s_["p10"], s_["p90"]])
        for y in ("2024", "2025"):
            s_ = cons_stats[y]
            w.writerow(["Sottoinsieme conservativo: affidamenti diretti <=140.000 €, parole chiave sviluppo+software, esclusi manutenzione/PNRR/adesioni (filtro nostro)", y, s_["n"], s_["q1"], s_["mediana"], s_["q3"], s_["p10"], s_["p90"]])
    # report testuale
    for name, o in groups:
        print("\n" + name)
        for y, s in o.items():
            if s["n"]: print(f"  {y}: n={s['n']:5d}  Q1={s['q1']:>9,}  mediana={s['mediana']:>9,}  Q3={s['q3']:>9,}  (P10={s['p10']:,} P90={s['p90']:,})")
            else: print(f"  {y}: n=0")
    print("\nFasce di importo (n):", fasce)
    print("Procedure:", proc.most_common(6))
    print("\nPer CPV a 5 cifre (primi 15):")
    for k, s in list(by5s.items())[:15]:
        print(f"  {k}: n={s['n']} mediana={s['mediana']:,} Q1={s['q1']:,} Q3={s['q3']:,}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("fetch", "all"): fetch()
    if cmd in ("analyze", "all"): analyze()
