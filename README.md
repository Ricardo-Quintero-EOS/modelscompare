# modelscompare

Browser interattivo per i prezzi live dei modelli GitHub Copilot. Mostra chiaramente la distinzione di contesto (Default vs Long Context, soglie token) e di reasoning (`🧠 Reasoning` vs `Standard`), oltre ai 4 costi separati (input, cached read, cached write e output). Catalogo, prezzi e metadati di intelligenza sono letti dinamicamente a ogni avvio.

## Installazione

Richiede Python 3.10+ e una connessione Internet.

```powershell
python -m pip install -e ".[test,build]"
modelscompare
```

Al primo avvio il setup riutilizzabile chiede solo quali modelli ti interessano e quali formati usare per l'export. Puoi selezionare più modelli e CSV, Excel o entrambi; nessuna selezione di modello significa mostrare tutti i modelli.

## Interfaccia e Navigazione

L'interfaccia a terminale offre una visualizzazione moderna con banner colorato, badge di stato, tabella a colonne (`MODELLO`, `CONTESTO`, `TIPO`, `INPUT`, `CACHED-R`, `CACHED-W`, `OUTPUT`) e scheda dettagli del modello evidenziato.

- Frecce su/giù: seleziona un modello; Home/End e PageUp/PageDown spostano la selezione.
- Invio: apre la scheda Artificial Analysis del modello selezionato.
- Spazio: aggiunge o rimuove il preferito selezionato (indicato con `★`).
- `M`: aggiunge o rimuove il modello dalla selezione di confronto (indicato con `✓`).
- `C`: attiva la modalità confronto mostrando solo i modelli selezionati; `Esc` torna all'elenco completo.
- `A`: alterna tutti i modelli e i preferiti.
- `S`: riapre il setup in qualsiasi momento.
- `E`: avvia l'export, chiedendo conferma prima di scrivere file.
- `R`: ricarica prezzi e catalogo live.
- `Q` o Ctrl+C: esce.

Le impostazioni sono memorizzate in `%APPDATA%\modelscompare\config.json` su Windows (o nella cartella di configurazione XDG su Linux/macOS). `--setup` riapre il wizard; `--config-file` seleziona un profilo diverso. Le selezioni precedenti in `selection.json` sono migrate automaticamente.

## Filtri e comandi

```powershell
modelscompare --provider OpenAI --category Powerful
modelscompare --model GPT --tier "Long context" --sort cached_read
modelscompare --status GA --threshold 272K --sort output --unit credits
modelscompare --sort cached_write --limit 10 --no-export
modelscompare --setup
modelscompare --all-models
modelscompare --export --output-prefix confronto_settembre
```

Filtri testuali case-insensitive si applicano come sottostringhe. Sono disponibili `--model`, `--provider`, `--category`, `--tier`, `--status`, `--threshold` (ripetibili), `--sort` (`name`, `provider`, `input`, `cached_read`, `cached_write`, `output`), `--unit` (`usd`, `credits`), `--limit`, `--all-models` e `--no-export`. Il flag esplicito `--export` autorizza l'export anche in batch; l'azione interattiva `E` chiede conferma. `--no-export` disabilita anche l'azione `E`.

## Export

I file vengono creati solo dopo conferma e salvati nella cartella `Downloads`. Se il nome esiste già, o un file è aperto in Excel, viene scelto il primo nome libero aggiungendo `_1`, `_2` e così via senza sovrascrivere gli export precedenti. I formati CSV e Excel si configurano dal wizard; `--output-prefix` cambia il nome base senza spostare i file. Ogni costo esporta colonne numeriche separate per USD e crediti AI per milione di token. L'Excel include filtri, intestazione congelata, formati numerici, link ai modelli e righe leggibili; nessuna colonna combina costi diversi.

## Distribuzione Windows

Per creare un pacchetto portatile per i colleghi, esegui una volta:

```powershell
.\package-windows.ps1
```

Condividi `dist\modelscompare-windows-x64.zip`. Il collega estrae lo ZIP e avvia `ModelsCompare.exe`: non deve installare Python o dipendenze. Serve una connessione Internet per caricare i prezzi live. La configurazione resta nel profilo Windows dell'utente e gli export vanno nella sua cartella `Downloads`.

La build usa PyInstaller in modalità console; il pacchetto è per Windows x64 e non è firmato digitalmente. La wheel Python rimane disponibile con `python -m build --wheel` per chi preferisce installare da sorgente.

Per pubblicare una release GitHub con EXE e ZIP allegati, crea e invia un tag versione dopo aver pubblicato le modifiche:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

GitHub Actions crea la release automaticamente. Dopo la prima release, il pacchetto può essere proposto al catalogo pubblico winget; il comando `winget install` sarà disponibile quando il manifest verrà accettato.

## Sorgenti e test

Il parser riconosce dinamicamente le tabelle di prezzo e i valori AI-credit/USD pubblicati; non mantiene elenchi statici di modelli. Le richieste di rete e il parsing sono separati per consentire test con fixture.

- https://docs.github.com/copilot/reference/copilot-billing/models-and-pricing
- https://artificialanalysis.ai/models

```powershell
python -m pytest
```
