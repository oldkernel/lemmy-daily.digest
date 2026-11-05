# Intro

Architettura: userei Gmail come servizio di consegna, senza acquistare un dominio.
Non serve necessariamente un servizio SMTP esterno a pagamento.
La soluzione che prenderei in considerazione è la Gmail API.

## Architettura proposta

1. Cloudflare Cron Trigger
2. 07:30 ogni mattina
3. Python Worker
4. RSS Lemmy + recupero articoli
5. Cloudflare Workers AI per traduzione
6. Analisi e sintesi giornalistica in italiano
7. Gmail API
8. Invio del messaggio HTML

La tua casella Gmail

Rassegna stampa pronta da leggere

Il vantaggio è che Gmail API utilizza HTTPS e quindi si integra bene con Cloudflare Workers, senza dover gestire un server SMTP. Google mette a disposizione l'API senza costi aggiuntivi per l'utilizzo ordinario.

Dovremo configurare una volta sola:

1. Un progetto su Google Cloud Console.
2. Abilitare Gmail API.
3. Configurare OAuth 2.0 con il permesso `gmail.send`.
4. Salvare le credenziali e il refresh token nei Cloudflare Secrets, mai nel repository Git.

Documentazione: [Gmail API](https://developers.google.com/workspace/gmail/api).

## Come procederei

Realizzerei il progetto in modo incrementale:

1. Recupero RSS Lemmy e selezione dei post.
2. Recupero e lettura degli articoli originali.
3. Integrazione Workers AI per la sintesi.
4. Generazione di una newsletter HTML gradevole.
5. Invio automatico tramite Gmail API.
6. Cron Trigger giornaliero alle 07:30.

Così avresti due piccoli progetti indipendenti, facili da mantenere e aggiornare.

# Step 1

Perfetto! Procediamo con calma e un passaggio alla volta, così costruiamo un progetto pulito e facilmente manutenibile.

Creiamo un nuovo progetto chiamato `lemmy-daily-digest`, usando:

- Python 3.12
- `uv` per la gestione dell'ambiente Python
- Cloudflare Workers con `pywrangler`
- Cloudflare Workers AI per la sintesi
- Cloudflare KV per tenere traccia delle notizie già elaborate
- Gmail API per l'invio
- Cron Trigger per la pianificazione

Non tocchiamo il tuo progetto `mastodon-rss`.

## Fase 1 – Configurazione Gmail API

Per prima cosa dobbiamo autorizzare il nostro Worker a inviare email dal tuo account Gmail.

La procedura si fa una volta sola tramite Google Cloud Console.

### 1. Crea un progetto Google Cloud

Apri:

[Google Cloud – Create Project](https://console.cloud.google.com/projectcreate?utm_source=chatgpt.com)

- Project name: `lemmy-daily-digest`
- Organization: lascia il valore predefinito, se non ne hai una.
- Clicca Create.

### 2. Abilita Gmail API

Una volta creato il progetto:

1. Apri [Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com?utm_source=chatgpt.com).
2. Verifica che sia selezionato il progetto `lemmy-daily-digest`.
3. Clicca Enable.

### 3. Configura OAuth

Apri [Google Auth Platform](https://console.cloud.google.com/auth/overview?utm_source=chatgpt.com).

Dovremo configurare:

| Campo              | Valore             |
| ------------------ | ------------------ |
| App name           | Lemmy Daily Digest |
| User support email | Il tuo Gmail       |
| Audience           | External           |
| Contact email      | Il tuo Gmail       |

Nella sezione Audience aggiungeremo il tuo indirizzo Gmail come Test user.

Attenzione a un dettaglio importante: Google fa scadere dopo 7 giorni i refresh token delle applicazioni External lasciate in modalità Testing, quando utilizzano scope Gmail. Per un'automazione quotidiana dovremo quindi portare l'app in modalità Production, pur mantenendola destinata al solo uso personale. Potrebbe comparire un avviso di app non verificata durante l'autorizzazione.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://developers.google.com\&sz=32)

developers.google.com+1

Per ora fermiamoci qui.

Quando hai creato il progetto, abilitato Gmail API e configurato la schermata OAuth, dimmelo.

Nel passaggio successivo creeremo le credenziali OAuth e genereremo il refresh token direttamente sul tuo Fedora, senza mai mettere password o credenziali personali nel codice Python.

# Step 2

Ottimo. Ora generiamo il refresh token sul tuo Fedora. Useremo un piccolo progetto Python separato, così non tocchiamo il tuo Worker `mastodon-rss`.

Il programma aprirà il browser per farti autorizzare l'accesso al tuo account Google. Richiederemo soltanto il permesso `gmail.send`, necessario per inviare email.

### 1. Crea il progetto Python

Apri un terminale e lancia:

```
mkdir -p ~/bin/python/lemmy-daily-digest
cd ~/bin/python/lemmy-daily-digest

uv init --python 3.12
uv add google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 2. Copia il file OAuth

Copia il JSON scaricato da Google nella directory appena creata e rinominalo:

```
credentials.json
```

Proteggi il file:

```
chmod 600 credentials.json
```

### 3. Crea lo script di autorizzazione

Crea un file chiamato `auth.py`:

### 4. Esegui l'autorizzazione

```
uv run python auth.py
```

Dovrebbe aprirsi il browser:

1. Seleziona il tuo account Gmail.
2. Conferma i permessi richiesti.
3. Se Google mostra l'avviso che l'app non è verificata, controlla che sia la tua applicazione e prosegui con l'opzione per continuare, se disponibile.
4. Al termine, il terminale dovrebbe confermare l'autorizzazione.

Nella directory troverai anche:

```
token.json
```

Importante

&#x20;Questo file contiene il refresh token: non condividerlo, non caricarlo su GitHub e non incollarlo in chat.

Aggiungiamo subito entrambi i file sensibili a `.gitignore`:

# Step 3

Refresh token valido e presente

Abbiamo quindi completato la parte Google OAuth. Adesso dobbiamo trasferire le credenziali su Cloudflare in modo sicuro: il Worker userà il `refresh_token` per ottenere automaticamente nuovi access token e inviare la rassegna al tuo Gmail.

Non caricheremo mai `credentials.json` o `token.json` su GitHub.

### 1. Inizializziamo il Worker Python

Per tenere separate le credenziali OAuth dal codice del Worker, creiamo una sottodirectory `worker`.

Nel terminale:

```
cd ~/bin/python/lemmy-daily-digest

mkdir worker
cd worker

uvx --from workers-py pywrangler init
```

È il comando indicato dalla documentazione Cloudflare per inizializzare un progetto Python Workers.

Durante la procedura:

- Nome del progetto: `lemmy-daily-digest`
- Scegli un template Python minimale, se ti viene chiesto.
- Se ti chiede di installare le dipendenze, conferma.

La struttura che vogliamo ottenere sarà simile a questa:

```
lemmy-daily-digest/
├── auth.py
├── credentials.json
├── token.json
├── .gitignore
├── pyproject.toml
└── worker/
    ├── pyproject.toml
    ├── wrangler.jsonc
    └── src/
        └── entry.py
```

### 2. Per ora fermiamoci qui

Non carichiamo ancora i segreti su Cloudflare: prima voglio verificare che il progetto Python Worker sia stato creato correttamente.

Quando hai eseguito `pywrangler init`, incollami l'output del terminale (puoi oscurare eventuali identificativi personali). Poi configureremo i segreti Gmail e le risorse Cloudflare.

Una nota: il Cron Trigger di Cloudflare usa l'ora UTC. Dovremo quindi gestire il passaggio tra ora solare e legale per mantenere l'invio alle 07:30 italiane.

# Step 4

Perfetto!
Pywrangler funzionante

Abbiamo quindi:

- Progetto `lemmy-daily-digest` creato.
- Python 3.12 configurato con `uv`.
- `workers-py` e `workers-runtime-sdk` installati.
- Comando `pywrangler` funzionante tramite `uv run`.
- Credenziali Gmail OAuth e refresh token generati.

Prossimo passo: configurare il Worker Cloudflare.

Prima creiamo la struttura del progetto e il file `wrangler.jsonc`, poi configureremo:

1. Il Cron Trigger per le 07:30.
2. Il binding KV per memorizzare i post già elaborati.
3. I segreti OAuth Gmail.
4. L'accesso a Workers AI per generare le sintesi in italiano.

# Step 5

`uv run pywrangler dev`
Il primo richiede qualche minuto perché Pywrangler prepara l'ambiente Pyodide e le dipendenze.

-> Ricordare che uv è installato come pacchetto Fedora e va aggiornato con DNF eventualmente

Adesso verifichiamo anche la parte più importante per il nostro progetto: l'esecuzione del metodo `scheduled()`, che domani dovrà avviare automaticamente la rassegna.

### 1. Riavvia con il supporto ai test Cron

Nel terminale dove gira il server premi `Ctrl+C`, poi esegui:

```
uv run pywrangler dev --test-scheduled
```

### 2. Simula un'esecuzione programmata

Apri un secondo terminale e lancia:

```
curl "http://localhost:8787/cdn-cgi/handler/scheduled?cron=*+*+*+*+*"
```

Cloudflare prevede questo endpoint per testare i Cron Trigger dei Python Workers.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://developers.cloudflare.com\&sz=32)

Cloudflare Workers docs+2



### 3. Controlla il primo terminale

Dovresti vedere il messaggio:

```
Lemmy Daily Digest: scheduled event received
```

Se compare, abbiamo verificato che il metodo `scheduled()` funziona.

# Step 6

Perfetto!&#x20;

Test superato



Abbiamo verificato che:

- Il Worker Python si avvia correttamente.
- Pywrangler gestisce l'ambiente.
- Il metodo `scheduled()` viene eseguito quando riceve un evento programmato.

Ora possiamo passare a Cloudflare.

### Prossimo passo: autenticazione

```
uv run pywrangler login
```
3\. Si aprirà il browser: accedi al tuo account Cloudflare e autorizza Pywrangler.

Quando torni al terminale, esegui:

```
uv run pywrangler whoami
```

Dovresti vedere il tuo account Cloudflare.

Fermiamoci lì e dimmi se l'autenticazione è riuscita. Nel passaggio successivo creeremo il namespace KV `LEMMy_CACHE` e lo collegheremo al Worker. Useremo il binding KV per evitare di elaborare ripetutamente gli stessi post.

Una nota: il Cron Trigger è già configurato, ma ricontrolleremo l'orario prima del deploy, così da garantire le 07:30 italiane anche nei giorni del cambio dell'ora legale.
-> Il cron è definito in wrangler.jsonc


# Step 7

Perfetto. Creiamo adesso lo spazio KV su Cloudflare: sarà il piccolo archivio in cui il Worker conserverà gli identificativi dei post già elaborati, evitando duplicati nelle rassegne successive.

### 1. Crea il namespace KV

Dalla directory del progetto, esegui:

```
uv run pywrangler kv namespace create LEMMY_CACHE
```

Se il comando va a buon fine, Cloudflare restituirà un identificativo simile a:

```
id = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

La documentazione Cloudflare descrive questo comando per creare un namespace KV.


Quando termina, incollami l'output, in particolare il namespace ID. Non serve condividere alcuna credenziale. Poi lo inseriremo in `wrangler.jsonc` per collegare il KV al Worker.

-> Questo id va poi messo in wrangler.jsonc

# Step 8 - Le credenziali !!!

Ottimo! Il binding KV è riconosciuto e il Worker parte correttamente. Adesso configuriamo le tre credenziali Gmail come Secrets di Cloudflare.

Ci servono:

- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`

In questo modo non saranno contenute né in `entry.py` né in `wrangler.jsonc`.

### 1. Recupera i valori sul tuo Fedora

Dalla directory del progetto, esegui questi comandi uno alla volta:

```
jq -r '.installed.client_id' credentials.json
```

```
jq -r '.installed.client_secret' credentials.json
```

```
jq -r '.refresh_token' token.json
```

Se `jq` non è installato:

```
sudo dnf install jq
```

I valori appariranno nel terminale: non incollarli qui e non inserirli in file di codice.

### 2. Carica i tre Secrets su Cloudflare

Esegui il primo comando:

```
uv run pywrangler secret put GMAIL_CLIENT_ID
```

Quando compare la richiesta del valore, incolla il `client_id` recuperato prima e premi Invio.

Ripeti per gli altri due:

```
uv run pywrangler secret put GMAIL_CLIENT_SECRET
```

```
uv run pywrangler secret put GMAIL_REFRESH_TOKEN
```

Ogni comando ti chiederà il valore da inserire. Incollalo direttamente nel terminale.

### 3. Cosa abbiamo ottenuto

Cloudflare conserverà le credenziali in modo protetto e le renderà disponibili al Worker attraverso l'oggetto `env`.

Una precisazione: questi Secrets sono caricati su Cloudflare, non automaticamente nell'ambiente locale `pywrangler dev`. Per i test locali predisporremo successivamente un file `.dev.vars` protetto e ignorato da Git.

Fermiamoci quando hai caricato tutti e tre i Secrets. Dimmi se i tre comandi sono terminati correttamente; non serve mostrarmi i valori.

Queste variabili le mettiamo anche in .dev.vars
Cloudflare utilizza proprio .dev.vars per fornire i Secrets durante lo sviluppo locale.

# Step 9 - Proviamo a mandare un mail

In locale dopo avere modificato entry.py:

`uv run pywrangler dev --test-scheduled`

e 

`curl "http://localhost:8787/cdn-cgi/handler/scheduled?cron=*+*+*+*+*"`

Dovrebbe fare arrivare una mail su gmail.

# Step 10

0. Recupero dei post dalla community Lemmy
1. Recupera l'URL dell'articolo originale.
2. Scarica la pagina web.
3. Estrae il testo principale, eliminando menu, pubblicità e contenuti accessori.
4. Conserva titolo, fonte e URL originale.
5. Gestisce gli articoli non accessibili senza bloccare tutta la rassegna.

Il punto 3 è complesso, usiamo la libreria:
`uv add trafilatura`

