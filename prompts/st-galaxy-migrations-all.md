1. Go to `https://st-galaxy.dontouch.group/migrations/(menu:create)`
2. In `Selezione profilo di partenza` type `{{ST_SOURCE_PHONE}}`, click `Cerca`, under `Azioni` click `Seleziona`
3. In `Seleziona profilo di destinazione` type `{{ST_DESTINATION_PHONE}}`, click `Cerca`, under `Azioni` click `Seleziona`
4. Click on `Prosegui` button
5. In `Wallet`, type the available amount  if present and click on the arrow button.
6. In `Info profilo`, click on the arrow button next to `Info`, `Media`, `Recensioni`, flag if an item has a lock instead of the arrow button and skip to step 7.
7. In `Prodotti`, click on the arrow button next to `Abbonamento` 
8. Click on `Prosegui` button
9. Click on each `Prosegui con OTP` toggles to disable them
10. Click on `Crea nuovo` button
11. After some seconds, it automatically redirects to `https://st-galaxy.dontouch.group/migrations`, on the table check that the first row, under `Stato` column
12. If `Stato` is `Completato con errori`, click on `Visualizza` under `Azioni` column , highlight what item has a red cross due to migration errors, likely `Media` and add that to the QA report.
