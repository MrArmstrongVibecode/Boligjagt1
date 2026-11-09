# bolig-bot

Holder øje med nye lejeboliger hos **Kereby** og **City Apartment** og sender en
push-besked via [ntfy](https://ntfy.sh), når der dukker en ny bolig op, som
passer til dine kriterier. Kører automatisk hver 15. minut i GitHub Actions.

## Sådan virker den

| Udlejer | Kilde | Bemærkning |
|---|---|---|
| Kereby | HTML fra `kereby.dk/bolig/` | Hvert kort har `data-*`-attributter (id, status, postnr, værelser, husleje, m²). |
| City Apartment | JSON fra `cityapartment.dk/wp-json/wp/v2/cityapartments` | WordPress' åbne REST-API. Hvis den fejler, læses `/all-properties/` som HTML i stedet. Erhverv og parkering sorteres fra via kategorien. |

Hver 15. minut sker følgende:

1. Begge udlejere hentes, hver for sig (én henvendelse pr. side). Fejler den ene, kører den anden videre.
2. Alle boliger filtreres efter kriterierne i `bolig_bot/config.py`.
3. Resultatet sammenlignes med `data/seen.json`.
4. Der sendes besked om **nye ledige boliger, der matcher**. Ellers sendes intet.
5. `data/seen.json` og `data/health.json` committes tilbage til repoet.

**Regler for beskeder**

- Reserverede og udlejede boliger giver ikke besked. Bliver en af dem ledig senere (og matcher), får du besked.
- "Ny, men reserveret": En helt ny bolig, der matcher, men allerede er reserveret, når botten ser den første gang, giver én besked (`NOTIFY_NEW_RESERVED`). Bliver den senere ledig, får du en almindelig "Ny bolig"-besked.
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

### 4. Test at beskeder når frem
*Actions → bolig-bot → Run workflow* → sæt flueben i **test_notify** → Run.
Du får en besked med titlen "TEST - Ny bolig: ..." på telefonen. Den henter
ingen sider og ændrer ikke `seen.json`. Kommer der ingen besked, så tjek at
secret'en `NTFY_TOPIC` er stavet præcis som kanalen i appen.

### 5. Præcis timing med cron-job.org (anbefalet)
GitHubs egne planlagte kørsler bliver ofte forsinket eller droppet (typisk
1-2 i timen i stedet for 4). [cron-job.org](https://cron-job.org) (gratis)
starter i stedet workflowet via GitHubs API til tiden.

**a) Token i GitHub** (dit profilbillede → Settings → Developer settings →
Personal access tokens → **Fine-grained tokens** → Generate new token):
- Repository access: **Only select repositories** → `Boligjagt1`
- Permissions → Repository permissions → **Actions: Read and write**
- Expiration: fx 1 år. Skriv datoen ned, og lav en ny token, når den udløber.

**b) Job i cron-job.org** (Create cronjob):
- URL: `https://api.github.com/repos/MrArmstrongVibecode/Boligjagt1/actions/workflows/bolig-bot.yml/dispatches`
- Advanced → Request method: **POST**
- Headers: `Accept: application/vnd.github+json`, `Authorization: Bearer <token>`,
  `X-GitHub-Api-Version: 2022-11-28`, `Content-Type: application/json`
- Request body: `{"ref":"main"}`
- Time zone: **Europe/Copenhagen**
- Svaret skal være **204** (= succes uden indhold).

Brug to jobs: et hvert 3. minut kl. 8-12 og et hvert 10. minut resten af døgnet.

## Lokalt

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q                       # tests (bruger gemte HTML/JSON-snapshots)
python -m bolig_bot --dry-run             # hent og vis alt, uden at sende eller gemme
python -m bolig_bot --dry-run --no-seed   # vis hvilke boliger der ville give besked lige nu
python -m bolig_bot --only kereby --dry-run
python -m bolig_bot --test-notify --dry-run   # vis testbeskeden uden at sende
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

### Gratis minutter
Offentlige repoer har ubegrænsede gratis minutter i GitHub Actions. Gør du
repoet privat, får du 2.000 minutter/md, og hver kørsel tæller som et helt
minut. Kørsel hver 15. minut (ca. 2.980 min/md) er så for meget. Ret cron i
`.github/workflows/bolig-bot.yml` til `"7,37 * * * *"` (hver halve time).
Kanalnavnet er en GitHub Secret og kan ikke ses af andre, heller ikke i et
offentligt repo.

Bemærk også, at GitHubs cron ikke er præcis. Kørsler kan blive forsinket
5-30 minutter eller i sjældne tilfælde springes over.

## Høflighed
- Én henvendelse pr. side pr. kørsel, dvs. 4 i timen (City Apartment: HTML kun hvis API'et fejler).
- User-Agent: `bolig-bot (privat brug; hentes højst hvert 15. minut)`.
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
