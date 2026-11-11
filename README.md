# Jelena — chata pri lese

Cvičný projekt vizualizácie chaty pri lese. Cieľom je ukázať, ako AI-assisted Blender práca dokáže postupne vylepšiť existujúci editovateľný 3D model — od základnej scény k detailnejšiemu exteriéru a interiéru.

## Súbory

- `Jelena/Jelena.blend` — pôvodná scéna.
- `Jelena/Jelena_Realistic_v001.blend` — pracovná kópia.
- `Jelena/Jelena_3D.obj`, `Jelena/Jelena_Model.step`, `Jelena/Jelena_Podorys.dxf` — geometrické podklady.
- `Jelena/Jelena_Exterier.png`, `Jelena/Jelena_Dispozicia.png`, `Jelena/Jelena_Interier.png` — referenčné rendery.
- `Jelena_Studia.pdf` — architektonická štúdia.
- `Jelena/Zacni_tu.md` — pôvodný návod.

## Rýchly štart

1. Otvor `Jelena/Jelena_Realistic_v001.blend` v Blenderi 5.2.3 LTS.
2. Scéna **A • Chata pri lese** je hlavná; aktívna kamera je **A • Chata pri lese**.
3. Interiérová kamera je **C • Interiér pri terase**.
4. Render spustíš cez **Render → Render Image**.

## MCP

Lokálne spojenie Cursor → Blender cez `mcp-for-blender` a addon **MCP for Blender** na `127.0.0.1:9876`. Cursor MCP server sa volá `blender`.

## Projektové pravidlá

- AP: `.ap/AP.md`; projektové pravidlá: `AGENTS.md`.

## Stav

Foundation: AP pin, README, `.gitignore` a overené MCP spojenie. Prvý baseline render je v `evidence/foundation-001/`. Pracovný súbor je `Jelena/Jelena_Realistic_v002.blend`; opravené porovnanie z kamery A je v `evidence/vegetation-002/`.

## Baseline

- `evidence/foundation-001/camera-a.png` — porovnávací render z kamery A.
- `evidence/foundation-001/manifest.json` — nastavenia, hashe a výsledok vizuálnej kontroly.

## Poznámka

Fotorealizmus nie je cieľom prvého prechodu. Dôležitá je viditeľná kvalita, zachovaný layout a postupné, overiteľné zlepšovanie.
