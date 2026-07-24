# Changelog

## 2.1.1 — 24 luglio 2026

- Verificata la nuova build Steam 24346205 direttamente dai contenitori originali del gioco.
- Confermato che LOCRES inglese, LOCRES italiano e LOCMETA sono byte-identici alla build 24271369: zero chiavi nuove, rimosse o modificate.
- Confermata la copertura completa delle 38.751 stringhe già revisionate.
- Rilevato un nuovo identificatore interno nel widget `ASAUI_MainMenu_DLC_Selector`.
- Riestratto il widget originale, riapplicate le quattro sostituzioni italiane e rigenerato il trio IoStore sulla base UE5 corrente.
- Verificati il nuovo contenitore con `retoc` e il round-trip esatto di entrambi gli UEXP modificati.
- Ricostruito l'installer autonomo in un solo EXE con rilevamento esplicito della build 24346205.

## 2.1.0 — 18 luglio 2026

- Verificata la nuova build Steam 24271369 direttamente dai contenitori originali del gioco.
- Confermato che LOCRES inglese, LOCRES italiano e LOCMETA sono byte-identici alla build 24230788: zero chiavi nuove, rimosse o modificate.
- Estesa la compatibilità dell'installer al nuovo build senza alterare le 38.751 traduzioni già approvate.
- Rigenerato l'override dei widget DLC sulla nuova base UE5, includendo il GUID FText e gli oggetti di script aggiornati.
- Aggiunta all'EXE una nuova icona ARK con badge italiano, disponibile nelle risoluzioni Windows da 16 a 256 pixel.
- Ricostruito e verificato l'installer autonomo in un solo file.

## 2.0.2 — 16 luglio 2026

- Applicati 45 adattamenti editoriali per evitare italianizzazioni forzate di termini ormai comuni nel gaming italiano.
- Ripristinati contestualmente `Camera`, `Password`, `Display`, `Gameplay`, `Multiplayer`, `Online`, `Offline`, `Preset`, `Skin` cosmetica e `Ping`.
- Conservate le traduzioni italiane quando più naturali: `telecamera` nelle frasi descrittive, `pelle` e `carnagione` negli usi anatomici, `mostra/visualizza` per il verbo `display`.
- Aggiornato il glossario per distinguere anglicismi comuni da residui di localizzazione reali.
- Ricompilato e riestratto il PAK: 38.751 corrispondenze esatte, zero chiavi mancanti, extra o difformi.

## 2.0.1 — 16 luglio 2026

- Nuovo audit manuale mirato a menu, interfaccia, testi brevi e residui inglesi player-facing.
- Corrette 66 voci del catalogo: 36 etichette visibili classificate erroneamente come tecniche e 30 testi secondari o duplicati.
- Tradotti `FACE`, `Scalp`, `Brows`, `Foot Size`, `Camera`, `Character`, `Controls`, `Display`, `Password`, valori di opzione e gradi qualitativi rimasti in inglese.
- Corretti i widget del menu DLC che incorporavano direttamente `DLC PACKS` e `Owned` fuori dal catalogo di localizzazione.
- Ricompilato e riestratto il PAK: 38.751 corrispondenze esatte, zero chiavi mancanti, extra o difformi.
- Estesi installazione, controllo stato, backup e ripristino ai componenti dell'override UI, tutti verificati singolarmente tramite SHA-256.

## 2.0.0 — 16 luglio 2026

- Revisione editoriale manuale riga per riga di tutte le 38.751 voci del catalogo.
- Riscritte 11.351 voci rispetto alla v1.2.0, con controllo di contesto, terminologia, tono e lore.
- Eliminati gli ultimi residui inglesi sospetti e corrette ulteriori etichette innaturali nei menu, nell'interfaccia e nei testi brevi.
- Verificata la nuova build Steam 24230788: il catalogo ufficiale non ha aggiunto o rimosso stringhe rispetto alla build precedente.
- Ricompilato e riestratto il PAK: 38.751 corrispondenze esatte, zero chiavi mancanti, extra o difformi.
- Migliorato l'autodetect in presenza di più installazioni Steam e irrobustiti backup e ripristino con controlli SHA-256.
- Confermati zero errori strutturali, zero avvisi e zero decisioni editoriali aperte.

## 1.2.0 — 15 luglio 2026

- Secondo audit totale del catalogo, concentrato su menu, interfaccia e testi brevi.
- Riviste 1.783 voci rispetto alla v1.1.0: 1.782 dell'interfaccia e una descrizione composita.
- Corretti falsi amici e residui inglesi come `DORSO`, `SETTINGS`, `FEATURED`, `Vibration`, `Always`, `WEIGHT` e `DLC PACKS`.
- Uniformati pannello del campione, statistiche, opzioni avanzate, comandi contestuali e menu DLC.
- Copertura confermata: 38.751 / 38.751 voci della build 24159380, con zero errori strutturali e zero avvisi.
- Aggiornati PAK, dati pubblici e installer autonomo con la nuova revisione.

## 1.1.0 — 13 luglio 2026

- Audit completo aggiuntivo di interfaccia, comandi, sistemi di gioco e descrizioni.
- Corrette 315 voci emerse dall'audit finale, oltre ai casi segnalati tramite screenshot.
- Sistemati valori e schede di menu come `ATTIVO`, `DISATTIVATO`, `INDIETRO`, `IMPOSTAZIONI`, `TASTIERA`, `CONTROLLER`, `INTERFACCIA` e `ASPETTO`.
- Aggiornati i comandi contestuali e varie formulazioni innaturali o ancora in inglese.
- Installer irrobustito con istanza singola, aggiornamenti verificati obbligatoriamente tramite SHA-256, sostituzione sicura dell'EXE e stato più chiaro dopo gli aggiornamenti di ARK.
- Copertura confermata: 38.751 / 38.751 voci del catalogo della build 24159380, con zero errori strutturali e zero avvisi.

## 1.0.0 — 12 luglio 2026

- Revisione completa delle 38.751 stringhe italiane di ARK: Survival Ascended.
- Installer Windows autonomo in un solo file.
- Rilevamento tramite manifest Steam, librerie aggiuntive, percorsi comuni e selezione manuale.
- Controllo della build, verifica SHA-256, backup e ripristino.
- Controllo aggiornamenti tramite GitHub Releases.
