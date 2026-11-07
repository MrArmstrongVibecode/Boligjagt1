# bolig-bot

Holder øje med nye lejeboliger hos **Kereby** og **City Apartment** og sender en
push-besked via [ntfy](https://ntfy.sh), når der dukker en ny bolig op, som
passer til dine kriterier. Kører automatisk hver time i GitHub Actions.

## Sådan virker den

| Udlejer | Kilde | Bemærkning |
|---|---|---|
| Kereby | HTML fra `kereby.dk/bolig/` | Hvert kort har `data-*`-attributter (id, status, postnr, værelser, husleje, m²). |
| City Apartment | JSON fra `cityapartment.dk/wp-json/wp/v2/cityapartments` | WordPress' åbne REST-API. Hvis den fejler, læses `/all-properties/` som HTML i stedet. Erhverv og parkering sorteres fra via kategorien. |

Hver time sker følgende:

1. Begge udlejere hentes, hver for sig (én henvendelse pr. side). Fejler den ene, kører den anden videre.
2. Alle boliger filtreres efter kriterierne i `bolig_bot/config.py`.
3. Resultatet sammenlignes med `data/seen.json`.
4. Der sendes besked om **nye ledige boliger, der matcher**. Ellers sendes intet.
5. `data/seen.json` og `data/health.json` committes tilbage til repoet.

**Regler for beskeder**

- Reserverede og udlejede boliger giver ikke besked. Bliver en af dem ledig senere (og matcher), får du besked.
- "Ledig igen": har du fået besked om en bolig, som så bliver reserveret og senere ledig igen, får du én besked mere. Det kan slås fra med `NOTIFY_BACK_AVAILABLE = False`.
- En bolig, der forsvinder og kommer tilbage med samme id, giver ikke en ny besked.
- Fejler en udlejer to kørsler i træk (`FAIL_THRESHOLD`), får du **én** fejlbesked. Når den virker igen, får du én "virker igen"-besked.
- Hvis en side pludselig returnerer 0 boliger, behandles det som en fejl og ikke som "alt er væk". Der slettes intet.

## Kriterier

Ret i `bolig_bot/config.py`:

```python
MIN_ROOMS = 2
MAX_RENT = 16_000
AREAS = { "Østerbro": {"postnumre": [2100, 2150], "navne": ["østerbro", ...]}, ... }
```

Områder matches på postnummer (også udledt af adressen, hvis feltet mangler).
Kun hvis der slet ikke er noget postnummer, matches der på bydelsnavn.
Bemærk, at **2300** er med under Amagerbro, men postnummeret dækker også
Islands Brygge, Amager Øst og Sundby.

## Opsætning (én gang)

### 1. ntfy på telefonen
1. Installer appen **ntfy** (App Store / Google Play).
2. Find på et langt, tilfældigt kanalnavn. Alle, der kender navnet, kan læse med, så behandl det som en adgangskode. Fx `bolig-` efterfulgt af 12 tilfældige bogstaver og tal.
3. Tryk på **+** i appen, skriv kanalnavnet og abonnér (server: `ntfy.sh`).

### 2. GitHub-repo
1. Opret et tomt repo på GitHub (det må gerne være **privat**).
2. Push koden:
   ```bash
   git init && git add . && git commit -m "bolig-bot"
   git branch -M main
   git remote add origin https://github.com/<dit-brugernavn>/<repo>.git
   git push -u origin main
   ```
3. **Secret:** *Settings → Secrets and variables → Actions → New repository secret*
   Navn: `NTFY_TOPIC`, værdi: dit kanalnavn.
4. **Skriverettigheder:** *Settings → Actions → General → Workflow permissions* →
   vælg **Read and write permissions** → Save.
5. **Aktivér Actions:** Gå til fanen **Actions**, og klik på "I understand my workflows, go ahead and enable them", hvis den knap vises.

### 3. Første kørsel (seed)
*Actions → bolig-bot → Run workflow* → sæt flueben i **seed** → Run.

Seed gemmer alle nuværende boliger som "set" uden at sende noget. Herefter får
du kun besked om det, der er nyt. (Botten seeder også automatisk første gang,
den ser en udlejer, så du får aldrig en bunke beskeder om gamle boliger.)

Tjek, at der er kommet et commit "Opdater bolig-state" med filen `data/seen.json`.

## Lokalt

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q                       # tests (bruger gemte HTML/JSON-snapshots)
python -m bolig_bot --dry-run             # hent og vis alt, uden at sende eller gemme
python -m bolig_bot --dry-run --no-seed   # vis hvilke boliger der ville give besked lige nu
python -m bolig_bot --only kereby --dry-run
NTFY_TOPIC=din-kanal python -m bolig_bot  # rigtig kørsel lokalt
```

## Fejlfinding

| Problem | Løsning |
|---|---|
| Ingen beskeder overhovedet | Det er normalt, hvis intet nyt matcher. Kør `--dry-run --no-seed` lokalt eller med *dry_run* i Actions, og se i loggen, hvorfor hver bolig er afvist (fx `husleje: 17550`). |
| `NTFY_TOPIC mangler` i loggen | Secret'en er ikke oprettet eller er stavet forkert. |
| `Permission denied` ved push i *Commit state* | Workflow permissions skal stå på **Read and write** (trin 2.4). |
| Fejlbesked "X virker ikke" | Siden er nede eller har ændret opbygning. Se loggen i Actions. Ved ændret opbygning skal parseren i `bolig_bot/sources/` rettes, og der skal gemmes en ny fixture i `tests/fixtures/`. |
| Vil teste beskeder | Ret midlertidigt `MAX_RENT` lokalt, slet `data/seen.json`, og kør `--dry-run --no-seed`. |
| Vil starte forfra | Slet `data/seen.json` og `data/health.json`, commit, og kør seed igen. |

### Vigtigt: GitHub slår planlagte kørsler fra efter 60 dage
I repoer uden aktivitet deaktiverer GitHub `schedule` efter 60 dage. Botten
committer `data/seen.json`, når der sker ændringer (`last_seen` opdateres højst
én gang i døgnet), og det holder normalt repoet aktivt. Får du en mail fra
GitHub om, at workflowet er deaktiveret, eller ser du ingen nye kørsler under
*Actions*, så klik **Enable workflow** under Actions → bolig-bot.

Bemærk også, at GitHubs cron ikke er præcis. Kørsler kan blive forsinket
5-30 minutter eller i sjældne tilfælde springes over.

## Høflighed
- Højst én henvendelse pr. side pr. time (City Apartment: HTML kun hvis API'et fejler).
- User-Agent: `bolig-bot (privat brug; hentes højst 1 gang i timen)`.
- robots.txt (tjekket nov. 2026) tillader begge lister. Kereby forbyder kun `/files/*`, City Apartment kun `/wp-admin/`. Der er ikke fundet brugsvilkår, som forbyder automatisk hentning.

## Struktur
```
bolig_bot/
  config.py          # dine kriterier
  sources/kereby.py  # henter + parser Kereby
  sources/cityapartment.py
  filters.py         # område / værelser / husleje
  state.py           # ny-logik, seed, fejlstatus
  notify.py          # ntfy
  main.py            # CLI
data/                # state (committes af Action'en)
tests/fixtures/      # gemte snapshots af siderne
```
