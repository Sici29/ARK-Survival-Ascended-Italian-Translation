# ARK — Traduzione italiana v2.1.1

Questa release rende la traduzione compatibile con il nuovo aggiornamento Steam di ARK.

## Verifica del nuovo aggiornamento

- Build Steam verificata: `24346205`.
- Catalogo inglese: 38.751 stringhe, identiche alla build precedente.
- Catalogo italiano ufficiale: 33.254 stringhe, identiche alla build precedente.
- Chiavi nuove, rimosse o modificate: zero.
- Copertura della revisione italiana confermata: 38.751/38.751.

Il controllo è stato eseguito sui LOCRES e sul LOCMETA originali estratti direttamente da `pakchunk0-Windows.pak`, senza usare la patch italiana né contenuti di mod.

## Menu DLC rigenerato

L'aggiornamento ha modificato l'identificatore interno associato a un testo del widget `ASAUI_MainMenu_DLC_Selector`. Il vecchio override non è stato riutilizzato: i widget sono stati riestratti dalla build 24346205, le quattro sostituzioni italiane sono state riapplicate e il trio IoStore è stato ricreato sulla base UE5 corrente.

Il contenitore supera `retoc verify`; il round-trip conserva esattamente entrambi gli UEXP modificati.

## Installazione

Scarica soltanto `ARK-Survival-Ascended-Traduzione-Italiana.exe`, chiudi ARK e avvialo. L'installer rileva automaticamente la copia regolarmente installata, verifica la build 24346205, crea un backup e installa tutti i componenti italiani incorporati controllandone singolarmente l'hash SHA-256.

Per usare la traduzione è necessaria una copia regolarmente installata di ARK: Survival Ascended. Le mod, compresa Play As Dino, non sono incluse.
