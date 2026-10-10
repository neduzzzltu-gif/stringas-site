---
name: bulk-check
description: Lean bulk progreso patikra iš Samsung Health eksporto (svoris, kalorijos, baltymai, miegas, žingsniai, treniruotės). Naudok, kai vartotojas parašo „pačekink“, „bulk check“, „kaip sekasi bulkas“, „patikrink progresą“ ar įkelia Samsung Health eksportą.
---

# Bulk check

## 1. Rask naujausią eksportą
1. Google Drive: `search_files` aplanke **„Samsung Health“** – imk naujausią `.zip` arba CSV failus (pagal modifikavimo datą).
2. Atsisiųsk į `scratchpad/shealth/<data>/` (kiekvienas eksportas – atskiras tuščias aplankas).
3. Jei Drive nėra arba atsisiųsti nepavyksta – paprašyk vartotojo įkelti ZIP tiesiai į pokalbį.

## 2. Paleisk ataskaitą
```bash
python3 -I .claude/skills/bulk-check/bulk_report.py <zip arba aplankas> --weeks 8
```
Tikslo tempas pagal nutylėjimą 0.5–1.5 % kūno svorio per mėnesį. Jei vartotojas nurodė kitą – perduok `--min`/`--max`.

## 3. Atsakyk lietuviškai, trumpai
- Lentelė (paskutinės savaitės).
- Verdiktas: tempas per lėtas / geras / per greitas ir konkretus kcal pakeitimas.
- Tik tai, kas iš duomenų matyti blogai, surikiuota nuo blogiausio: baltymai < 1.6 g/kg, miegas < 7 h, mažiau treniruočių nei įprastai, kcal labai šokinėja.
- Jokių komplimentų. Jei kurių nors duomenų nėra (pvz., nevedamas maistas) – pasakyk, kad tos eilutės negalima įvertinti.
