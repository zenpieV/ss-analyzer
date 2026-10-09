# SS Analyzer — Overlay Theme Catalogue (v1, 24 themes)

Design contract (from theme-factory + design-system + hallmark):
each theme = **layout + tokens + motion**, never a palette swap alone.
Tokens follow three layers (primitive → semantic → component); when a theme
demands it, the overlay may change size, orientation, and button/menu layout.
The analysis body text must stay readable in every theme (min contrast guard
noted per theme). Joke themes are jokes in chrome only — results stay intact.

Engine note for implementation: one `THEMES` registry in app.py; each entry
carries `geometry` (w/h or orientation), `regions` (header/body/footer order),
`qss` (full stylesheet), and `flags` (opacity, font, extras like scanlines).
Switching = rebuild card widget + apply QSS. No config.json changes needed.

**Status: ALL 65 themes IMPLEMENTED** (`THEMES` registry in app.py; tray-only
Theme submenu; choice in `settings.json`). Nothing pending.

## C. Pass-2 catalogue additions (all implemented)

- **#17 Noir Typewriter** — sepia paper, Courier, red-stamp minimalism; typewriter reveal.
- **#18 Arcade Cabinet** — neon marquee, INSERT COIN strip, candy buttons.
- **#19 Zen Garden** — pine-on-ricepaper calm, hover-only footer, haiku status.
- **#20 Solarized Lab** — precision instrument, calibration voice.
- **#21 High-Contrast ADA** — 7:1+ yellow-on-black, oversized everything, no motion.
- **#22 Win95 Chrome** — bevels, navy title bar, sunken wells, `Ready` status.
- **#23 Hologram** — scanlines, clipped-corners energy, cyan wireframe.
- **#24 Field Notes** — sticky yellow, red margin rule, paperclip-tag buttons.

## D. Fandom pass (all implemented — design DNA per fandom)

- **Elden Ring** — grace-gold serif on tomb-black, message-appraisal voice (`message appraised`), blood-red Close, `YOU DIED` error line.
- **Hollow Knight** — pale-on-abyssal-blue elegance, Focus/Dream Nail/Rest buttons, `soul refilled`.
- **Sekiro** — ink-black minimalism, red 死 seal, Strike/Deflect/Resurrect, `hesitation is defeat` errors.
- **Minecraft** — dirt-dark UI, stone buttons, yellow splash floater, `achievement get!`, Quit Game.
- **Pokédex FRLG** — GBA double-border textbox, `▼ A: continue`, DATA/CRY/CLOSE, `registered!`.
- **GTA Vice City** — neon-pink/teal chrome on midnight, gradient spinner, Change Disk.
- **GTA San Andreas** — grove-green slabs, `1992` strip, Respect+/Busted pair.
- **GTA V** — Franklin-green Pricedown energy, Switch/Stocks/Busted.
- **JoJo** — menacing purple-gold, floating ゴ glyphs, Joestar ☆, ORAORA/MUDA/To Be Continued.
- **Cuphead** — 1930s cream/ink/red Technicolor revue, Applaud/Encore/Exit Stage.
- **Manga** — black-gutter panels, ドン!! SFX floater, Next Page/Bookmark, つづく.
- **Marvel** — red-box masthead, italic shout buttons, `excelsior!`.
- **DC** — elite midnight-blue minimalism, Case File button, `justice logged`.
- **Halo** — UNSC hologram cyan + scanlines, CORTANA LINK strip, Spartan/Cortana/Power Down.
- **Resident Evil** — typewriter Courier, VHS `REC ▶` strip, merchant Buy/Sell, typewriter reveal.
- **FNaF** — camera-static purple-black, `NIGHT 1 · POWER 98%`, Check Cams/Wind Box/6 AM.
- **FNF** — four colored arrow floaters, EQ bars, SICK!! scoring voice.
- **Mario** — sky-blue shell, ?-block dot, 1-UP/Save & Quit/Game Over, `course clear!`.
- **BioShock** — art-deco gold/teal letterspacing, `would you kindly` voice throughout.
- **Borderlands** — hazard-yellow cel slabs, italic shout, `badass rank +1`.
- **Persona 5** — red-black-white starbursts, slanted Showtime buttons, `treasure secured`.
- **Tekken** — aggressive italic, GET READY strip, FIGHT! alarm banner on load.
- **Destiny 2** — thin light letterspaced calm, tricorn ▲, `eyes up, guardian`.
- **Batman** — yellow-oval title bar, Detect/Case Files/I'm Batman, justice voice.
- **Fallout NV** — amber terminal typewriter, `WAR. WAR NEVER CHANGES.`, Pip-Boy button.
- **Steampunk** — brass/copper leather, gear floaters, `pressure nominal`.
- **Cyberpunk 2077** — hazard-yellow title slab, Trauma-Team ticker, Preem/Fixer/Flatline.
- **Ghostwire Tokyo** — spectral cyan + torii red, 祓 exorcism floater, Purge button.
- **Skyrim** — stone-gray formality, dragon-divider strip, Fus/Quest Log/Ro Dah.
- **Baldur's Gate** — dark-gold d20 energy, Roll Insight/Long Rest, crit success/fail lines.
- **Dispatch SDN** — comic-clean office navy/orange, Handbook p.44 strip, Deploy/Roster/End Shift.
- **Terraria** — dirt-and-grass earth tones, Dig/Craft/Save & Exit, `achievement get!`.
- **Zelda** — deep-green triforce gold, Take This/Save/It's Dangerous.
- **RuneScape** — brown-and-yellow 2000s UI, XP DROP strip, Bank/Quest Journal/Logout.
- **ULTRAKILL** — SmileOS red title bar, MANKIND/BLOOD/HELL strip, typewriter reveal, RIP/TEAR/REPENT, `S+ · ULTRAKILL`.
- **Stellar Blade** — platinum minimalism, ember-orange accent, `RECLAIM EARTH FOR HUMANKIND`, Scan/Legacy/Rest at Camp.

## E. Feminine pass + app parity (all implemented)

- **Coquette** — verified coquette palette (#FFF3FA/#FFE1ED/#ECBAD0/#C78CA0, ink #1C1B18), Georgia italic, bow floaters, `sealed with a bow`.
- **Strawberry Milk** — milk-carton cream/red, shake-well strip, Sip/Refill/All Gone.
- **Lavender Haze** — night-plum dreaminess, moon + sparkle floaters, Dream/Stargaze/Wake Up.
- **Discord** — 1-to-1 dark tokens (#313338/#2B2D31/#1E1F22/#383A40, text #DBDEE1/#B5BAC1, blurple #5865F2, green #57F287): channel-name header, Today divider, BOT status with live timestamp, red-hover close.
- **Aseprite** — verified theme accents (selection red #ff5555, tooltip yellow #ffff7d, titlebar slate #7c909f, hot cream #ffebb6) on dark-mode panels, radius-0 pixel chrome, mono everywhere, Layer/Cel status strip.

---

## A. Requested themes

### 1. YoRHa Interface (NieR:Automata)
Pseudo-diegetic android OS overlay. Warm beige paper `#c3bda8`, panel `#b0ab98`,
ink blocks `#4b413d`, near-zero extra color (canon: Yoko Taro's beige order).
- Layout: 460px wide, left icon rail with ◆ diamond bullets; header bar is a
  dark muddy block with cream text; footer buttons are flat beige slabs.
- Type: clean grotesk, letterspaced small-caps labels (`SYSTEM`, `LOG`, `POD-042`).
- Signature: diamond ◆ list markers, thin double-rule dividers, "musical score"
  hairlines behind the header, status line `CHECKING… NO HOSTILES DETECTED`.
- Motion: panels slide in with fluid "moist" easing; loading = cascading dots.
- Build: QSS flat fills + custom paint for hairlines; header text set to
  `POD 042 — SUPPORT UNIT`.
- Guard: body keeps `#4b413d` on `#c3bda8` (high contrast despite soft palette).

### 2. Clawd Terminal (Claude Code)
The overlay becomes a terminal pane: bg `#1a1a1a`, fg `#c3c1ba`,
accent Claude coral `#d87757`, success sage `#51a556`.
- Layout: full-width short bar (560×220), single monospace stream; header is a
  `$ ss-analyze --model <name>` command line; no separate buttons — footer is a
  `> [copy] [open-log] [close]` hint line, clickable.
- Type: monospace everywhere (Consolas/Cascadia Mono).
- Signature: ASCII spinner `⠋⠙⠹` while analyzing, `✓`/`✗` status glyphs,
  coral `❯` prompt marker before the result.
- Motion: text streams in (typewriter reveal, fast); spinner animates.
- Build: QTextBrowser monospace + QSS; footer buttons restyled as `[bracketed]`
  text buttons; spinner via QTimer swapping glyphs.
- Guard: keep `#c3c1ba` on `#1a1a1a`; coral reserved for accents, never body.

### 3. Digital Diva 01 (Hatsune Miku)
Concert-stage futurism: near-black `#0b0e14`, Miku turquoise `#39c5cf`,
white, hot-pink `#ff5c8a` sparingly.
- Layout: tall narrow card (360×520, portrait); header holds a fake 5-band
  equalizer; model dropdown styled as a setlist selector.
- Type: geometric sans headers, tabular numerals, glowing `01` watermark.
- Signature: equalizer bars dance while analyzing; turquoise glow border;
  footer buttons as piano-key strips (white keys + black keys).
- Motion: EQ animates on analyze; card opens with a quick vertical wipe.
- Build: QSS glow via layered borders; EQ = 5 QLabel bars driven by QTimer.
- Guard: body text pure white at 15px+ on near-black; pink never behind text.

### 4. stdout (minimal CLI)
The anti-theme: almost no chrome. Transparent background, one monospace block,
no card, no border, no buttons (text fades after 12s; full text in log).
- Layout: 420px wide, height fits content; single region only.
- Tokens: fg `#e8e8e8` with soft text-shadow for legibility over any wallpaper.
- Type: 12px monospace, dim gray timestamp prefix.
- Signature: `Copy`/`Close` exist only as a hover-reveal micro-row.
- Motion: fade in/out (opacity animation); nothing else.
- Build: frameless transparent dialog, no `#card` frame; QTimer auto-hide.
- Guard: text-shadow + optional 40% black scrim behind text only.

### 5. Girly-Pop Overdrive
Sticker-bomb pop: bubblegum `#ff8fc7`, cream `#fff3f8`, lilac `#c9b6ff`,
ink `#5b2340`. Chunky rounded everything.
- Layout: 440px card, oversized header with waving sparkle dividers;
  buttons are pill-shaped with thick outlines and drop shadows.
- Type: rounded bold headers, body stays clean sans for readability.
- Signature: ✿ ♡ ⋆ stickers as static decorations (corners only, never over
  text), "omg results!!" header voice, pastel progress hearts while loading.
- Motion: springy pop-in (overshoot easing); stickers do one gentle wiggle.
- Build: QSS large radii (18px), 3px borders, drop-shadow via QGraphicsEffect.
- Guard: decorations pinned to margins; body on cream, never on pink.

### 6. Sensory Overload (overstimulation/clutter, deliberate)
Maximalist dashboard parody that still works: ticker tape, badges, sparkline,
fake "LIVE" dot, confetti corners — body text quarantined in a calm reader box.
- Layout: wide 600px, three zones: chaos header (ticker + badges), calm body
  (plain reader panel), arcade footer (big candy buttons).
- Tokens: near-black base so the neon clutter (lime, cyan, magenta, amber)
  doesn't murder contrast; body panel always `#f5f2ea` paper.
- Type: mixed — condensed shout headers, clean serif-free body.
- Signature: scrolling ticker (`ANALYZING… WOW… PIXELS…`), badge row
  (`100% AI`, `NO HUMANS`, `✨ FRESH`), fake viewer count that ticks up.
- Motion: ticker scrolls, badges pulse; body panel never animates.
- Build: ticker = marquee QLabel on QTimer; badges = styled QLabels; reader
  panel is a nested QFrame with its own calm QSS.
- Guard: THE rule of this theme — clutter may touch everything except the
  reader panel.

### 7. Doge (meme)
2013 forum energy: Comic Sans, rotated `wow` / `such pixels` / `very analyze`
labels floating at angles, Shiba palette (tan `#d8b078`, brown `#6b4a2f`).
- Layout: standard card + 4 absolutely-positioned rotated caption labels.
- Type: Comic Sans MS everywhere, rainbow-ish caption colors.
- Signature: captions avoid the body box; header reads `much results. wow.`
- Motion: captions drift 2px on open, then freeze (restraint = funnier).
- Build: caption QLabels with rotation via transform; everything else default.
- Guard: captions never overlap body text; body stays 13px+.

### 8. Emergency Meeting (Amogus meme)
Red-alert crewmate aesthetic: emergency red `#c51111`, dark corridor gray,
chunky alarm header `EMERGENCY MEETING`.
- Layout: card topped by a full-width alarm banner; footer primary button
  relabeled `EJECT (Close)`, secondary `Skip Vote (Copy)`.
- Type: heavy condensed headers, mono body.
- Signature: alarm banner flashes red/dark during analysis then holds solid;
  status line reports `1 IMPOSTOR REMAINING (the screenshot)`.
- Motion: banner flash loop while loading only; static after.
- Build: QTimer toggles banner QSS class; button text overrides per theme.
- Guard: flash rate ≤2Hz, stops on result (photosensitivity).

### 9. 404 Theme Not Found (pun)
The theme pretends it failed to load: giant `404`, "the theme you requested
could not be found", then results delivered anyway as the "error details".
- Layout: error-page composition — huge numeral, centered message, body as
  a faux server-log block below.
- Tokens: server-gray `#2b2f36`, amber warning `#e8a33d`, off-white text.
- Type: mono for the log block, grotesk for the 404.
- Signature: footer buttons `Go Back (Close)` and `Report Issue (Copy)`;
  status line `this is fine.`;
- Motion: 404 types itself out, cursor blink; body fades in after.
- Build: layout reorder (numeral region added above header) + QSS.
- Guard: the joke is one screenful — body log block keeps full contrast.

### 10. Comic Sans-ational (pun)
A legal-memo parody set entirely in Comic Sans: "RE: YOUR SCREENSHOT —
FINDINGS (FORMAL-ish)". Parchment `#f7f1de`, ink `#33302a`, red stamp.
- Layout: memo format — TO/FROM/DATE/RE header block instead of a title bar;
  body is the memo; footer is signature line + `Sincerely, the computer`.
- Type: Comic Sans MS, 12pt body. All of it. No exceptions. That's the joke.
- Signature: rotated `CERTIFIED SILLY` stamp in red outline; paperclip emoji 📎.
- Motion: stamp slams in with a thud scale (once).
- Build: header region replaced by memo fields; stamp = rotated QLabel.
- Guard: 12pt minimum, parchment contrast — silliness must stay legible.

### 11. It's Not a Bug, It's a Theme (pun)
Styled as a bug tracker ticket: `ISSUE #404 — screenshot observed`,
labels (`wontfix`, `works-on-my-machine`), assignee `you`.
- Layout: ticket layout — title row + label chips + comment-thread body
  (each paragraph rendered as a "comment" from `maintainer-bot`).
- Tokens: tracker white `#ffffff`, chip pastels, link-blue `#0969da`.
- Type: system sans, small dense metadata.
- Signature: footer `Close as completed (Close)` / `Copy stack trace (Copy)`;
  status `marked as completed by arlecchino`.
- Motion: comments slide in staggered, 60ms apart.
- Build: body paragraphs split into chip-bordered comment frames.
- Guard: chips small but ≥11px; comment text full contrast.

---

## B. Originals

### 12. Obsidian Glass (current default, refined)
Dark glassmorphism baseline everything else deviates from: `#111620` @93%,
indigo `#7c9cff` border, 14px radius. The control theme.
- Layout: current card (header/body/footer stacked, 380–520px).
- Keep as the readability reference all joke themes must match or beat.

### 13. Thermal Receipt
Results print as a shop receipt: white `#fafafa` paper, mono ink `#222`,
zigzag tear edge top/bottom, `*** THANK YOU ***` footer.
- Layout: narrow 320px column; header = store name `SS MART · ORDER #<time>`;
  buttons become `REPRINT (Copy)` / `NO RECEIPT (Close)`.
- Signature: dashed separators, barcode strip (fake, decorative) under body.
- Motion: receipt "prints" — body reveals top-to-bottom on open.
- Build: tear edge via repeated `▲▼` glyph row or painted polygon; reveal via
  progressive plaintext append on QTimer.
- Guard: 12px mono minimum on white.

### 14. Brutalist Slab
Raw concrete: 3px black borders, zero radius, no shadows, system font,
safety-orange `#ff4d00` single accent. Buttons are slabs that invert on hover.
- Layout: same regions, hard rectangles, visible grid gaps.
- Signature: uppercase stamped labels, `◼` bullets, underline links.
- Motion: none. Instant cuts only. (Motion is decoration; decoration is banned.)
- Build: QSS only — borders, radius 0, flat fills.
- Guard: orange never behind text.

### 15. CRT Phosphor
Green-phosphor terminal `#33ff66` on `#0a0f0a`, scanline overlay, soft glow,
slight barrel illusion via vignette.
- Layout: terminal stream like theme 2 but distinct: prompt `C:\SS>`,
  response as printed lines with `>` continuations.
- Signature: scanlines (repeating-linear-gradient equivalent via painted
  overlay), occasional single-frame glitch offset on open.
- Motion: typewriter reveal + faint flicker (opacity 0.97–1.0 loop, subtle).
- Build: scanline QLabel overlay with striped pixmap; flicker via QTimer.
- Guard: flicker amplitude tiny; phosphor green ≥4.5:1 on near-black.

### 16. Blueprint
White linework on blueprint blue `#1e4d8c`: corner ticks, dimension labels
(`420 × 300`), dashed frames, grid backdrop.
- Layout: card becomes a "drawing sheet" — title block bottom-right
  (DWG NO. SS-01, SCALE 1:1, DRAWN: ss-analyzer).
- Type: technical mono/condensed, uppercase.
- Signature: measurement labels on card edges; buttons as revision boxes
  (`REV A — Copy`).
- Motion: draw-on effect — border dashes march once on open.
- Build: painted border overlay + title-block footer region.
- Guard: linework decorative; body text white on solid blue panel.

### 17. Noir Typewriter
Sepia paper `#e8dcc0`, ink `#2a241d`, red ribbon accents `#a33b2e`,
typewriter mono (Courier New), coffee-ring stain corner.
- Layout: letter format — dateline, `Dear Analyst,` body, sign-off footer.
- Signature: `CASE FILE #<date>` stamp header; red circle around key sentence
  is NOT drawn (we don't know the key sentence — restraint).
- Motion: typewriter reveal with carriage `ding` spacing (visual only).
- Build: QSS paper texture via subtle gradient; stain = static pixmap corner.
- Guard: Courier ≥12px; sepia contrast checked.

### 18. Arcade Cabinet
Neon arcade: magenta `#ff2fb3` + cyan `#00e5ff` on near-black, chrome marquee
header `★ SS ANALYZER ★`, `INSERT COIN` blinking footer.
- Layout: marquee header (big, centered), screen-bezel body (inset, scanlined),
  control-deck footer (round candy buttons: red/yellow/green circles).
- Signature: `1UP` score counter showing character count; coin slot divider.
- Motion: marquee chase-lights (alternate two border colors on timer);
  `INSERT COIN` blinks until first result.
- Build: round buttons via border-radius 50%; bezel via nested frames.
- Guard: blink ≤2Hz; body inside bezel keeps white-on-black.

### 19. Zen Garden
Radical calm: warm white `#faf8f2`, single pine accent `#4a6741`, enormous
whitespace, one hairline enclosure, no buttons visible until hover.
- Layout: 480px, 40px padding, header reduced to a small seal-stamp square;
  body is the whole card; footer hover-reveal only.
- Type: light-weight grotesk, generous line-height 1.7.
- Signature: a single ensō circle (static SVG-ish paint) behind the header;
  status line is a haiku (`pixels settle / meaning rises like steam / log keeps all`).
- Motion: 600ms slow fade. Nothing else. Ever.
- Build: QSS spacing + hover-reveal footer; ensō via painted arc.
- Guard: hairline borders ≥1px `#4a6741` at 40% — visible but quiet.

### 20. Solarized Lab
Precision instrument in Solarized: base3 `#fdf6e3` paper, base00 `#657b83`
ink, blue `#268bd2` primary, magenta `#d33682` for model name only.
- Layout: lab-report grid — left metadata gutter (model/time/size) + right
  result column; footer as instrument controls.
- Type: mono metadata, serif-free clean body.
- Signature: precision footer (`±0.0 FLUFF · CALIBRATED`), thin rule grid.
- Motion: none on open; numbers tick once (decorative counter).
- Build: two-column body region (new sub-layout) + QSS.
- Guard: Solarized pairs chosen from the contrast-safe set only.

### 21. High-Contrast ADA
Accessibility-first: pure black `#000`, yellow `#ffd800` text/borders,
28px minimum body, full keyboard operation, focus rings everywhere.
- Layout: larger card (560px+), single column, oversized buttons (56px tall),
  model switcher as large radio list instead of dropdown.
- Type: bold sans, 1.6 line-height, no thin weights anywhere.
- Signature: focus-visible outlines on every control; status via text + icon.
- Motion: none (vestibular safety); instant state changes.
- Build: QSS scale-up + focus QSS; dropdown replaced by list widget.
- Guard: IS the guard — 7:1+ everywhere, verified pairs only.

### 22. Win95 Chrome
Gray bevels `#c0c0c0`, navy title bar `#000080` with white bold text,
Tahoma 11px, chunky raised buttons with 2px outset borders.
- Layout: classic window — title bar with `_ ▢ ✕` (min/max decorative,
  ✕ closes), menu row (`File Copy | View Log | Help Close`), status bar
  with sunken panels at the bottom.
- Signature: pixel-tahoma, dotted focus rects, sunken body well.
- Motion: none. Windows appear. (That is the whole philosophy.)
- Build: QSS bevels via border-style outset/inset; title bar custom widget.
- Guard: navy/white + black-on-gray are natively high contrast.

### 23. Hologram
Cyan wireframe `#7df9ff` on deep blue-black `#050a14`, 45° clipped corners,
corner brackets, faint grid, scan-beam sweep on analyze.
- Layout: clipped-corner card (octagon-ish), header as `◤ SCAN // SS-ANALYZER`;
  footer buttons as bracketed segments `[ COPY ]`.
- Signature: scan beam (bright horizontal line) sweeps body during analysis;
  corner brackets pulse once on result.
- Motion: sweep loop while loading; settle to static on result.
- Build: clipped corners via mask or painted path; beam = animated QLabel.
- Guard: cyan text only for labels; body white `#eaf6ff` on dark.

### 24. Field Notes
Sticky-note archaeology: legal-pad yellow `#fff3a3`, red margin line, tape
corners, slight 1.5° rotation, handwriting-style headers (caveat: use a casual
sans, not a real handwriting font, for legibility).
- Layout: note card with margin gutter; header is a circled date + title in
  casual caps; footer as torn edge with buttons as paper-clipped tags.
- Signature: masking-tape strips top corners, red margin rule, `★ important`
  doodle next to the model name.
- Motion: note drops in with a tiny rotate-settle (1.5° → 0.8°).
- Build: rotation via transform on the card frame; tape = semi-transparent
  beige QLabels; margin = painted line.
- Guard: rotation ≤1.5° so body lines stay readable; ink `#33302a` on yellow.

---

## Shortlist recommendation
Ship order by effort/value: **12** (already exists) → **2** (terminal crowd =
you) → **1** (signature piece, matches the menu-girl canon) → **4** (trivial,
validates the engine) → **13/14** (cheap QSS-only proofs of structural range).
Joke themes land best as a batch (7–11) once the switcher UI exists.

Next step when approved: theme engine (`THEMES` registry + switcher UI in
overlay/tray, same pattern as the model switcher) — say which 3–5 to build first.
