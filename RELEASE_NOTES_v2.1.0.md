# ARK — Traduzione italiana v2.1.0

Questa release rende la traduzione compatibile con il nuovo aggiornamento Steam di ARK e introduce la nuova icona dell'installer con badge italiano.

## Verifica del nuovo aggiornamento

- Build Steam verificata: `24271369`.
- Catalogo inglese: 38.751 stringhe, identiche alla build precedente.
- Catalogo italiano ufficiale: 33.254 stringhe, identiche alla build precedente.
- Chiavi nuove, rimosse o modificate: zero.
- Copertura della revisione italiana confermata: 38.751/38.751.

Il controllo è stato eseguito sui LOCRES e sul LOCMETA originali estratti direttamente da `pakchunk0-Windows.pak`, senza usare la patch italiana né contenuti di mod.

I widget DLC fuori catalogo sono stati riestratti e rigenerati sulla nuova base UE5: l'aggiornamento ha modificato un GUID FText e gli oggetti di script interni, mentre le correzioni visibili `PACCHETTI` e `TUOI` restano invariate.

## Nuova icona

L'unico EXE della release usa ora un'icona ARK dedicata con badge italiano, coerente con gli installer Aniimo e Star Citizen e completa delle risoluzioni Windows da 16 a 256 pixel.

## Installazione

Scarica soltanto `ARK-Survival-Ascended-Traduzione-Italiana.exe`, chiudi ARK e avvialo. L'installer rileva automaticamente la copia regolarmente installata, verifica la build, crea un backup e installa tutti i componenti italiani incorporati controllandone singolarmente l'hash SHA-256.

Per usare la traduzione è necessaria una copia regolarmente installata di ARK: Survival Ascended.
