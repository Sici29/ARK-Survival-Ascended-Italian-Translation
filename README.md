# ARK: Survival Ascended — Traduzione italiana

Revisione italiana amatoriale del catalogo di localizzazione di **ARK: Survival Ascended**, con installazione automatica, controllo della build, backup e ripristino.

## ☕ Sostieni il progetto

La traduzione viene revisionata e aggiornata gratuitamente. Se ti è utile e vuoi aiutarmi a mantenerla compatibile con le future versioni di ARK, puoi offrirmi un caffè.

[![Offrimi un caffè e sostieni la traduzione italiana](https://img.shields.io/badge/Offrimi_un_caff%C3%A8-Sostieni_la_traduzione-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=000000)](https://buymeacoffee.com/sici29)

**Grazie di cuore a chi sceglie di sostenere il progetto e le future traduzioni italiane.**

## Scarica e installa

### 1. Scarica un solo file

[**Scarica l'ultima versione da GitHub Releases**](https://github.com/Sici29/ARK-Survival-Ascended-Italian-Translation/releases/latest)

Il solo file necessario è:

```text
ARK-Survival-Ascended-Traduzione-Italiana.exe
```

### 2. Chiudi il gioco

Chiudi **ARK: Survival Ascended** prima di continuare.

### 3. Avvia l'installer

Fai doppio clic sull'EXE e premi **Invio**. Non servono Python, programmi aggiuntivi, archivi da estrarre o copie manuali.

L'installer:

- legge il manifest Steam ufficiale dell'App ID `2399830`;
- controlla tutte le librerie Steam, comprese quelle su dischi diversi;
- verifica la presenza reale di `ArkAscended.exe` e del PAK principale;
- mostra percorso, build rilevata e stato della traduzione;
- impedisce l'avvio simultaneo di più copie dell'installer;
- crea un backup prima di modificare qualsiasi file;
- copia la patch in modo atomico e ne verifica l'hash SHA-256;
- permette di ripristinare la situazione precedente dal menu.

### 4. Seleziona Italiano

Avvia il gioco e seleziona **Italiano** nelle impostazioni della lingua.

## Se ARK non viene trovato

Il rilevamento automatico usa, nell'ordine:

1. percorso già verificato e salvato;
2. manifest Steam e `libraryfolders.vdf`;
3. registro di Windows e librerie Steam aggiuntive;
4. unità locali e percorsi Steam comuni;
5. cartella dell'installer e cartella corrente.

Se nessun metodo trova una copia valida, compare una normale finestra di Windows. Seleziona la cartella che contiene `ShooterGame`:

```text
D:\SteamLibrary\steamapps\common\ARK Survival Ascended
```

La cartella viene accettata soltanto se contiene sia l'eseguibile del gioco sia `pakchunk0-Windows.pak`.

## Ripristina la situazione precedente

1. Chiudi ARK.
2. Apri nuovamente l'installer.
3. Digita `2` e premi **Invio**.

I backup vengono conservati in:

```text
Documenti\ARKItalianTranslation\backups
```

## Stato della traduzione

- Copertura: **38.751 / 38.751 stringhe**.
- Stringhe approvate editorialmente: **29.529**.
- Risorse tecniche preservate intenzionalmente: **9.222**.
- Build verificata: **24159380**.
- Versione della traduzione: **1.1.0**.
- Revisione: interfaccia, descrizioni, sistemi di gioco, tutorial, note e testi narrativi.
- Controlli finali: zero errori strutturali, zero avvisi e zero stringhe sospese.

## Aggiornamenti

L'installer controlla GitHub Releases all'avvio. Se trova una versione più recente può scaricare il nuovo EXE, verificarne dimensione e SHA-256 pubblicati da GitHub, sostituire la versione precedente in sicurezza e riaprirsi automaticamente. Un aggiornamento privo del digest ufficiale non viene installato.

Se ARK riceve una build non ancora verificata, l'installer non procede silenziosamente: mostra la nuova build e richiede un installer aggiornato. L'uso avanzato di `--force` resta disponibile da riga di comando.

## Limiti della copertura

Il dato **38.751 / 38.751** indica la copertura completa del catalogo di localizzazione estratto dalla build verificata. Messaggi diagnostici generati dal server o dal motore, testi costruiti dinamicamente e contenuti aggiunti da mod possono trovarsi fuori dal catalogo e quindi restare in inglese. Un esempio è il messaggio tecnico `Server hitch detected`, che non proviene dal file di localizzazione sostituito dalla patch.

## Crediti e collegamenti

Dal menu dell'installer puoi aprire:

- repository e release GitHub;
- sezione Issues per segnalare errori;
- pagina per sostenere il progetto.

Progetto e traduzione italiana: **Sici29**.

## Segnala un problema

Usa la sezione [Issues](https://github.com/Sici29/ARK-Survival-Ascended-Italian-Translation/issues) per segnalare:

- una frase poco naturale o rimasta in inglese;
- un termine incoerente;
- un testo tagliato nell'interfaccia;
- un problema con rilevamento, installazione o ripristino.

Allega uno screenshot e indica dove appare il testo.

<details>
<summary><strong>Informazioni per traduttori e sviluppatori</strong></summary>

Il repository contiene soltanto i sorgenti necessari alla manutenzione:

- `data/translation_it.csv`: chiavi e testi italiani completi, senza le frasi inglesi estratte dal gioco;
- `data/glossary_master.csv`: terminologia vincolante;
- `tools/ark_it_installer.py`: sorgente dell'installer;
- `tools/build_release.py`: generazione dell'EXE one-file;
- `tools/export_public_data.py`: esportazione byte-safe del master pubblico;
- `tests/`: controlli automatici per rilevamento, installazione e ripristino.

Il repository non contiene archivi originali di ARK né il PAK distribuibile. Il PAK verificato viene aggiunto soltanto durante la compilazione locale e incorporato nell'EXE pubblicato nella Release.

</details>

## Nota legale

Questa è una traduzione amatoriale non ufficiale e non è affiliata a Studio Wildcard, Grove Street Games, Snail Games, Epic Games o Valve. Per utilizzarla è necessaria una copia regolarmente installata di ARK: Survival Ascended.
