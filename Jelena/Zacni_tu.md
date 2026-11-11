# Jelená | Chata pri lese

Cvičný projekt pre ukážku postupu od výkresu po render. Vonkajší pôdorys chaty má 8,40 × 5,80 m. Terasa má približne 10,4 m². Les a terén sú vymyslené pre prezentáciu.

## Súbory

| Súbor | Obsah | Jednotky |
| --- | --- | --- |
| `Jelena_Podorys.dxf` | Kótovaný 2D pôdorys s vrstvami pre steny, otvory, nábytok a terasu | mm |
| `Jelena_Model.step` | 3D CAD telesá stien, podlahy, základovej dosky, štítov a strechy | mm |
| `Jelena_3D.obj` | Rovnaký stavebný objem vo formáte na import do Blenderu | m |
| `Jelena.blend` | Uložená scéna s materiálmi, nábytkom, terasou, lesom, svetlami a kamerami | m |
| `Jelena_Exterier.png`, `Jelena_Dispozicia.png`, `Jelena_Interier.png` | Hotové rendery pre ukážku | pixely |

DXF, STEP a OBJ vznikli z jedného geometrického podkladu. Steny, otvory a strecha sú súčasťou 3D stavebného objemu. Rámy, sklá, interiérové dvere, terasa, nábytok a les sa doplnili v Blenderi. Nábytok má v DXF zakreslené pôdorysné rozloženie. Podklad je architektonická štúdia na vizualizáciu.

## Prvé otvorenie

1. Rozbaľ ZIP do bežného priečinka.
2. V Blenderi otvor `Jelena.blend`. Scéna bola vytvorená a renderovaná vo verzii 4.3.2. Používa zabudované procedurálne materiály a geometriu.
3. V hornej lište otvor prepínač scény. **A • Chata pri lese** je kompletný model. **B • Zariadená dispozícia** zobrazuje pohľad so zrezanými stenami a skrytou strechou.
4. V scéne A je aktívna exteriérová kamera. Interiérovú kameru nájdeš v kolekcii **07 • Svetlá a kamery** pod názvom **C • Interiér pri terase**. Označ ju a v 3D okne zvoľ **View → Cameras → Set Active Object as Camera**. Render spustíš cez **Render → Render Image**.
5. Ak chceš vidieť import samostatne, otvor nový prázdny súbor a zvoľ **File → Import → Wavefront (.obj)**. Pre tento OBJ nastav **Forward Axis = Y**, **Up Axis = Z**, **Scale = 1**. Základová doska má mať 8,40 × 5,80 m. V rozbalenom projekte je už uložená aj celá pripravená scéna.

## Prvý pokus s AI

Pracuj na kópii .blend. Najprv nechaj AI identifikovať kameru, kolekciu nábytku a rozmery základovej dosky. Potom vyskúšaj jednu zmenu a porovnaj dva rendery z tej istej kamery.

> V scéne A uprav iba materiál pohovky na tehlovú farbu. Geometriu, rozmiestnenie, svetlá a aktívnu kameru ponechaj. Po úprave povedz názov zmeneného materiálu.

Vzorový projekt vznikol pomocou Pythonu a Blenderu. Blender MCP je voliteľná nadstavba na interaktívne riadenie Blenderu cez kompatibilného AI klienta.
