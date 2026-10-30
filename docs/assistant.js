/* ==================================================================== "Ask the data" assistant
   A deterministic question-answering helper that runs entirely in the browser. It reads only window.DASH (through
   the tables and helpers defined in index.html: S, TXT, tr, recFor, recsAll, SCEN, SNAT, ADOPT, DRVC, VAL, WF ...)
   and the knowledge-base texts below. No server, no API key, no external calls; it never invents numbers.
   Loaded after the main script in index.html. */
"use strict";

Object.assign(TXT.en, {
  as_title: "Ask the data", as_btn: "Ask", as_ph: "Ask about yields, inputs, districts…", as_send: "Send", as_close: "Close", as_you: "You",
  as_hello: "Hello! I answer only from this dashboard's results (NISR survey, satellite data, model). Ask about a district, crop or input, or pick a question below.",
  as_open: "Open on map", as_open_page: "Open page",
  as_yield: "{crop} yield in {d} ({season} {y}) was {v} kg/ha, {rank} of {n} districts{tgt}.",
  as_tgt: " and {p}% of the PSTA 5 target ({t} kg/ha)",
  as_yield_nat: "In {season} {y}, the average {crop} yield across {n} districts was {v} kg/ha. Highest: {hi}; lowest: {lo}.{tgt}",
  as_tgt_nat: " The PSTA 5 target is {t} kg/ha.",
  as_noyield: "NISR has no published {crop} yield for {d} in {season}{y}.",
  as_trend: "{crop} yield in {d} ({season}) went from {b} kg/ha in {by} to {l} kg/ha in {ly} ({c}). Over the same years the average of all districts changed by {nc}.",
  as_trend_nat: "The average {crop} yield across districts ({season}) went from {b} kg/ha in {by} to {l} kg/ha in {ly} ({c}). Biggest rises: {up}.",
  as_rec: "For {crop} in {d} ({season}), the best input is {lever}: about +{g}% yield, {t} t extra per season. It is already used on {a}% of the crop area.",
  as_rec_next: " Next best: {lever} (+{g}%, {t} t).",
  as_rec_none: "For {crop} in {d} ({season}), the surveyed inputs add little (under 1%). Other constraints matter more there: plot size, planting time, weather risk.",
  as_rec_nodata: "There are too few surveyed {crop} fields in {d} ({season}) to give a recommendation.",
  as_eff: "If farmers in {d} who do not use {lever} on {crop} started using it, yield would rise about {g}% ({t} t per season, {season}); {a}% of the area already uses it. Across Rwanda: +{ng}% ({nt} t).",
  as_eff_nat: "Across Rwanda, if farmers who do not use {lever} on {crop} started using it, {season} yield would rise about {ng}% ({nt} t per season).",
  as_eff_nod: " {d} has too few surveyed fields for its own estimate.",
  as_notscored: "{lever} is not scored for {crop}: too few surveyed plots use it, or too few do not.",
  as_top_lever: "Districts where {lever} adds the most {crop} ({season}): {list}.",
  as_top_best: "Districts with the largest extra {crop} harvest from their best input ({season}): {list}.",
  as_top_yield: "Highest {crop} yields in {season} {y}: {list}.",
  as_adopt: "In {d}, {lever} is used on {v}% of the {crop} area ({season} {y} survey); Rwanda: {nv}%.",
  as_adopt_all: "In {d} ({crop}, {season} {y} survey), inorganic fertilizer is used on {f}% of the area, improved seed on {s}% and manure on {m}% (Rwanda: {nf}%, {ns}% and {nm}%).",
  as_adopt_none: "There is no survey input-use figure for {lever} on {crop} in {d} ({season}).",
  as_drv: "For {crop}, inputs and practices explain {mg}% of the difference between high- and low-yield fields, season weather (satellite) {w}%, plot and farmer {p}%, soil and terrain {s}%. Top factors: {top}.",
  as_acc: "In districts it has never seen, the model estimates district yields within {e}% on average (a national average misses by {b}%). But for a new season, a district's own past yield is the best guide: {wf}% error against {wm}% for the best model. Use the model to compare inputs, not to replace the survey.",
  as_tgt_crop: "The PSTA 5 target for {crop} by 2028/29 is {t} kg/ha. The latest average across districts ({season} {y}) is {v} kg/ha, {p}% of the target.",
  as_tgt_none: "This dashboard has no PSTA 5 yield target for {crop} (targets: maize, beans, Irish potato, soybean, cassava, wheat).",
  kb_targets: "NST2 and PSTA 5 (2024/25–2028/29) aim to raise crop productivity by about 50% by 2028/29, and to raise smallholder use of inorganic fertilizer from 54.9% to 66.5% and of improved seed from 35.9% to 50%.",
  kb_data: "Data: NISR Seasonal Agricultural Survey published district yields 2017–2026 and plot microdata 2022–2025 (152,835 plot records). Satellite and geospatial data, extracted per district and season with Google Earth Engine: MODIS NDVI/EVI greenness and land temperature, CHIRPS rainfall, ERA5-Land soil moisture and air temperature, Sentinel-1 radar, iSDAsoil soil pH, carbon and nitrogen, SRTM elevation and slope, inside a cropland mask. Season weather from satellites explains about 27% of within-crop yield differences, soil and terrain about 18%.",
  kb_method: "A LightGBM model learns yield from 42 features (inputs, plot and farmer traits, soil, terrain, satellite weather) on 152,835 surveyed fields. For the scenarios, each 2025 field that does not use an input is predicted again as if it did (fertilizer at the typical dose), and the gains are added up with survey weights per district. An input is shown only if at least 200 surveyed plots use it and 200 do not.",
  kb_limits: "Gains are associations in survey data, not field-trial results. The public microdata have no plot GPS or sector codes, so satellite, soil and terrain data are district values (one per district and season). This limits plot-level accuracy (within-crop plot R² about 0.13–0.19), which is why results are given per district. With NISR's internal GPS-linked plots, the same pipeline could give field-level recommendations. For a new season, past district yield predicts better than the model.",
  kb_team: "Made by Rebecca Dukundimana and Jean de Dieu Niyogisubizo (University of Rwanda) for the NISR Big Data Hackathon 2026, Track 1. AI assistance (Claude, Anthropic) was used only to generate code; all code was reviewed, tested and approved by the team. The problem definition, data choices, analysis decisions and interpretation of results are the team's own.",
  kb_howto: "Choose a crop, season and district at the top left. Yield trends shows the change since a baseline year; What to do shows the best input per district (or pick one input); What drives yield and How reliable explain the model. Click a district on the map to select it, hover for values, and switch language in the side menu.",
  as_unknown: "I can answer questions about yields, trends, recommendations, inputs, drivers, model accuracy, data and methods. Try:",
  as_q1: "What should {d} do for {crop}?", as_q2: "{crop} yield in {d}", as_q3: "How has {crop} yield in {d} changed since 2018?",
  as_q4: "Top districts for fertilizer on {crop}", as_q5: "What drives {crop} yield?", as_q6: "How reliable is the model?"
});
Object.assign(TXT.rw, {
  as_title: "Baza amakuru", as_btn: "Baza", as_ph: "Baza ku musaruro, inyongeramusaruro, uturere…", as_send: "Ohereza", as_close: "Funga", as_you: "Wowe",
  as_hello: "Muraho! Nsubiza nkoresheje gusa ibisubizo by'iki gikoresho (ubushakashatsi bwa NISR, amakuru y'icyogajuru, icyitegererezo). Baza ku karere, igihingwa cyangwa inyongeramusaruro, cyangwa uhitemo ikibazo hasi.",
  as_open: "Fungura ku ikarita", as_open_page: "Fungura urupapuro",
  as_yield: "Umusaruro wa {crop} muri {d} ({season} {y}) wari {v} kg/ha, ku mwanya wa {rank} mu turere {n}{tgt}.",
  as_tgt: ", ugeze kuri {p}% by'intego ya PSTA 5 ({t} kg/ha)",
  as_yield_nat: "Mu {season} {y}, impuzandengo y'umusaruro wa {crop} mu turere {n} yari {v} kg/ha. Uri hejuru: {hi}; uri hasi: {lo}.{tgt}",
  as_tgt_nat: " Intego ya PSTA 5 ni {t} kg/ha.",
  as_noyield: "NISR nta musaruro wa {crop} yatangaje muri {d} mu {season}{y}.",
  as_trend: "Umusaruro wa {crop} muri {d} ({season}) wavuye kuri {b} kg/ha mu {by} ugera kuri {l} kg/ha mu {ly} ({c}). Muri iyo myaka, impuzandengo y'uturere twose yahindutseho {nc}.",
  as_trend_nat: "Impuzandengo y'umusaruro wa {crop} mu turere ({season}) yavuye kuri {b} kg/ha mu {by} igera kuri {l} kg/ha mu {ly} ({c}). Aho wiyongereye cyane: {up}.",
  as_rec: "Kuri {crop} muri {d} ({season}), inyongeramusaruro nziza ni {lever}: umusaruro wiyongeraho nka {g}%, ni ukuvuga toni {t} z'inyongera ku gihembwe. Isanzwe ikoreshwa kuri {a}% by'ubuso bw'iki gihingwa.",
  as_rec_next: " Ikurikiraho: {lever} (+{g}%, toni {t}).",
  as_rec_none: "Kuri {crop} muri {d} ({season}), inyongeramusaruro zo mu bushakashatsi zongera bike (munsi ya 1%). Hano izindi mbogamizi ni zo zikomeye: ingano y'umurima, igihe cyo gutera, ikirere.",
  as_rec_nodata: "Imirima ya {crop} yakozweho ubushakashatsi muri {d} ({season}) ni mike cyane ku buryo hatangwa inama.",
  as_eff: "Abahinzi bo muri {d} batakoresha {lever} kuri {crop} batangiye kuyikoresha, umusaruro wiyongeraho nka {g}% (toni {t} ku gihembwe, {season}); {a}% by'ubuso basanzwe bayikoresha. Mu Rwanda hose: +{ng}% (toni {nt}).",
  as_eff_nat: "Mu Rwanda hose, abahinzi batakoresha {lever} kuri {crop} batangiye kuyikoresha, umusaruro w'{season} wiyongeraho nka {ng}% (toni {nt} ku gihembwe).",
  as_eff_nod: " {d} ifite imirima mike yakozweho ubushakashatsi ku buryo itagira igereranyo ryayo.",
  as_notscored: "{lever} ntibyabazwe kuri {crop}: imirima ibikoresha cyangwa itabikoresha ni mike cyane.",
  as_top_lever: "Uturere {lever} yongeramo umusaruro mwinshi wa {crop} ({season}): {list}.",
  as_top_best: "Uturere dufite umusaruro w'inyongera wa {crop} mwinshi hakoreshejwe inyongeramusaruro nziza ya buri karere ({season}): {list}.",
  as_top_yield: "Uturere dufite umusaruro wa {crop} mwinshi mu {season} {y}: {list}.",
  as_adopt: "Muri {d}, {lever} ikoreshwa kuri {v}% by'ubuso bwa {crop} (ubushakashatsi bwa {season} {y}); mu Rwanda: {nv}%.",
  as_adopt_all: "Muri {d} ({crop}, ubushakashatsi bwa {season} {y}), ifumbire mvaruganda ikoreshwa kuri {f}% by'ubuso, imbuto z'indobanure kuri {s}%, ifumbire y'imborera kuri {m}% (mu Rwanda: {nf}%, {ns}% na {nm}%).",
  as_adopt_none: "Nta mubare w'ikoreshwa rya {lever} kuri {crop} muri {d} ({season}) uri mu bushakashatsi.",
  as_drv: "Kuri {crop}, inyongeramusaruro n'imihingire bisobanura {mg}% by'itandukaniro hagati y'imirima yera cyane n'iyera bike, ikirere cy'igihembwe (icyogajuru) {w}%, umurima n'umuhinzi {p}%, ubutaka n'imiterere yabwo {s}%. Ibintu by'ingenzi: {top}.",
  as_acc: "Mu turere kitigeze kibona, icyitegererezo kigereranya umusaruro w'akarere n'ikosa rya {e}% ugereranyije (impuzandengo y'igihugu yibeshyaho {b}%). Ariko ku gihembwe gishya, umusaruro w'akarere wabanje ni wo uyobora neza: ikosa rya {wf}% ugereranyije na {wm}% ku cyitegererezo cyiza. Icyitegererezo gikoreshwe mu kugereranya inyongeramusaruro, si mu gusimbura ubushakashatsi.",
  as_tgt_crop: "Intego ya PSTA 5 kuri {crop} mu 2028/29 ni {t} kg/ha. Impuzandengo iheruka y'uturere ({season} {y}) ni {v} kg/ha, ni ukuvuga {p}% by'intego.",
  as_tgt_none: "Muri iki gikoresho nta ntego ya PSTA 5 y'umusaruro wa {crop} irimo (intego zirimo: ibigori, ibishyimbo, ibirayi, soya, imyumbati, ingano).",
  kb_targets: "NST2 na PSTA 5 (2024/25–2028/29) bigamije kongera umusaruro w'ibihingwa ku buso hafi 50% bitarenze 2028/29, no kongera abahinzi bato bakoresha ifumbire mvaruganda kuva kuri 54.9% kugera kuri 66.5%, n'abakoresha imbuto z'indobanure kuva kuri 35.9% kugera kuri 50%.",
  kb_data: "Amakuru: umusaruro w'uturere watangajwe n'Ubushakashatsi bwa NISR ku buhinzi bw'ibihembwe 2017–2026, n'imibare y'ibanze y'imirima 2022–2025 (imirima 152,835). Amakuru y'icyogajuru n'ay'imiterere y'ubutaka, yakuwe na Google Earth Engine ku karere no ku gihembwe: icyatsi cy'ibihingwa NDVI/EVI n'ubushyuhe bw'ubutaka bya MODIS, imvura ya CHIRPS, ubuhehere bw'ubutaka n'ubushyuhe bw'umwuka bya ERA5-Land, radar ya Sentinel-1, pH, karubone na azote by'ubutaka bya iSDAsoil, ubutumburuke n'ubuhaname bya SRTM. Ikirere (icyogajuru) gisobanura hafi 27% by'itandukaniro ry'umusaruro ku gihingwa kimwe, ubutaka n'imiterere yabwo hafi 18%.",
  kb_method: "Icyitegererezo cya LightGBM kiga umusaruro gikoresheje ibintu 42 (inyongeramusaruro, umurima n'umuhinzi, ubutaka, imiterere y'ubutaka, ikirere cy'icyogajuru) ku mirima 152,835. Ku bigereranyo, buri murima wo mu 2025 udakoresha inyongeramusaruro wongera guhanurwa nk'aho uyikoresha (ifumbire ku ngano isanzwe), maze inyongera zigateranywa ku karere hakoreshejwe uburemere bw'ubushakashatsi. Inyongeramusaruro yerekanwa gusa iyo nibura imirima 200 iyikoresha n'indi 200 itayikoresha.",
  kb_limits: "Inyongera ni amasano agaragara mu bushakashatsi, si ibisubizo by'igerageza mu mirima. Imibare y'ibanze iboneka ku mugaragaro ntigira GPS y'imirima cyangwa kode z'imirenge, bityo amakuru y'icyogajuru, ubutaka n'imiterere yabwo ni ay'akarere (agaciro kamwe ku karere n'igihembwe). Ibi bigabanya ubushobozi ku rwego rw'umurima (R² hafi 0.13–0.19), ni yo mpamvu ibisubizo bitangwa ku karere. Hamwe na GPS y'imirima NISR ifite imbere mu kigo, uburyo bumwe bwatanga inama ku murima. Ku gihembwe gishya, umusaruro w'akarere wabanje uhanura neza kurusha icyitegererezo.",
  kb_team: "Cyakozwe na Rebecca Dukundimana na Jean de Dieu Niyogisubizo (Kaminuza y'u Rwanda) mu irushanwa NISR Big Data Hackathon 2026, Track 1. Ubufasha bwa AI (Claude, Anthropic) bwakoreshejwe gusa mu kwandika code; code yose yasuzumwe, igeragezwa kandi yemezwa n'itsinda. Gusobanura ikibazo, guhitamo amakuru, ibyemezo by'isesengura no gusobanura ibisubizo ni iby'itsinda.",
  kb_howto: "Hitamo igihingwa, igihembwe n'akarere hejuru ibumoso. 'Uko umusaruro uhagaze' herekana impinduka kuva mu mwaka fatizo; 'Icyo gukora' herekana inyongeramusaruro nziza kuri buri karere (cyangwa uhitemo imwe); 'Ibigena umusaruro' na 'Kwizerwa' hasobanura icyitegererezo. Kanda ku karere ku ikarita kugira ngo ugahitemo, shyira imbeba hejuru urebe imibare, uhindure ururimi mu ruhande.",
  as_unknown: "Nshobora gusubiza ibibazo ku musaruro, impinduka zawo, inama, inyongeramusaruro, ibigena umusaruro, kwizerwa kw'icyitegererezo, amakuru n'uburyo. Gerageza:",
  as_q1: "{d} yakora iki ku {crop}?", as_q2: "Umusaruro wa {crop} muri {d}", as_q3: "Umusaruro wa {crop} muri {d} wahindutse ute kuva 2018?",
  as_q4: "Uturere twa mbere ku ifumbire kuri {crop}", as_q5: "Ni iki kigena umusaruro wa {crop}?", as_q6: "Icyitegererezo cyizewe gute?"
});

const Ask = (() => {
  /* ---------------------------------------------------------------- parsing */
  const norm = t => String(t).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[’‘`]/g, "'").replace(/\s+/g, " ").trim();
  // order matters: specific names before generic ones
  const CROP_WORDS = [
    ["Sweet potato", /\bsweet ?potato|\bibijumba/], ["Irish potato", /\bpotato|\bibirayi/],
    ["Climbing bean", /\bclimbing bean|\bimishingiriro/], ["Bush bean", /\bbush bean|\bbigufi|\bbean|\bibishyimbo/],
    ["Maize", /\bmaize|\bcorn\b|\bibigori/], ["Cassava", /\bcassava|\bimyumbati/], ["Sorghum", /\bsorghum|\bamasaka/],
    ["Soybean", /\bsoy|\bsoya/], ["Wheat", /\bwheat|\b(i|ku )ngano\b(?! ?(y'|ya |yo |z'|isanzwe))/]
  ];
  const LEVER_WORDS = [
    ["package_fert_seed_manure", /\bpackage|\ball three|\bcombined|\bbyose hamwe|\bpaki/],
    ["manure", /\bmanure|\bcompost|\bi?mborera/], ["lime", /\blime\b|\bliming|\bishwagara/],
    ["anti_erosion", /\berosion|\bterrac|\bisuri|\bamaterasi/], ["improved_seed", /\bseed|\bi?mbuto/],
    ["fertilizer", /\bfertili[sz]|\bnpk\b|\bdap\b|\burea\b|\bifumbire/]
  ];
  const ADOPT_COL = { fertilizer: "fert", improved_seed: "seed", manure: "manure", lime: "lime", anti_erosion: "antierosion" };
  const has = (t, re) => re.test(t);
  const RE = {
    team: /\bteam\b|\bwho (made|built|created|developed)|\bauthors?\b|\bitsinda|\bnde\b|\bwakoze|\bai\b|\bclaude\b|\bartificial intel|\bubwenge bw/,
    howto: /how (do|can|should) (i|we) (use|read|navigate)|how to (use|read|navigate)|how does (the|this) dashboard|\buse (the|this) dashboard|\bnkoresha\b|\bnkoresha nte|\bgukoresha iki gikoresho|\bnte\b.*gikoresho|\bgisomwa/,
    limits: /\blimit|\bcaveat|\bweakness|\bgps\b|\bchallenge|\bshortcoming|\bi?mbogamizi|\baho bigarukira|\bintege nke/,
    accuracy: /\baccura|\breliab|\berror\b|\berrors\b|\btrust|\bvalidat|\bmape\b|\br2\b|\br²|\bkwizerwa|\bcyizewe|\bbyizewe|\bikosa|\bkwizera/,
    method: /\bmethod|\bhow (does|do|did) (the )?(model|scenario|estimate|recommendation)|\bhow (are|were|is) .*(calculated|computed|estimated)|\bshap\b|\blightgbm\b|\buburyo\b|\bmwabaze|\bbyabazwe|\bbibarwa/,
    data: /\bdata\b|\bdataset|\bsource|\bsatellite|\bsentinel|\bmodis\b|\bchirps\b|\bera5|\bearth engine|\bndvi\b|\bisdasoil|\bsrtm\b|\bamakuru\b|\bicyogajuru|\bibyogajuru/,
    targets: /\bpsta|\bnst ?2|\btarget|\bgoal|\bintego/,
    drivers: /\bdrive|\bdriver|\bfactor|\bexplain|\baffect|\bwhat matters|\binfluenc|\bdetermin|\bwhy (are|is|do)|\bkigena|\bbigena|\bigena\b|\bigitera|\bimpamvu/,
    top: /\btop\b|\bwhich district|\bwhat district|\bhighest|\bbest district|\branking|\brank\b|\bwhere\b|\bmost\b|\bu?tuhe\b|\bakahe\b|\btwa mbere|\bku isonga|\bdufite umusaruro mwinshi/,
    topGain: /\bgain|\bextra|\bopportunit|\bpriorit|\bpay|\binyongera|\btwunguka|\bkunguka/,
    effect: /what if|\bwould\b|\bcould\b|\bimpact|\beffect|\bgain|\bincrease|\braise|\bboost|\badd\b|\badds\b|\bshould .* use|\byakongera|\bbyakongera|\byazamura|\bbyazamura|\binyongera|\bingaruka|\bbakoresheje|\bbatangiye|\byongera/,
    adopt: /how many|\bshare\b|\bpercent|\badopt|\buse\b|\buses\b|\busing\b|\bused\b|\bbakoresha|\bikoreshwa|\bbangahe|\bbingahe|\bhakoreshwa/,
    rec: /\brecommend|\bshould\b|\bbest input|\bwhich input|\bwhat input|\bwhat to do|\badvice|\badvise|\bpriority|\bicyo gukora|\binama\b|\bbakwiye|\byakwiye|\bikwiye|\byakora|\bbakora|\bgukora iki|\bakora iki/,
    trend: /\btrend|\bchang|\bsince\b|\bgrow|\bincreas|\bdecreas|\bimprov|\bdeclin|\bover time|\bevolv|\bimpinduka|\bkuva\b|\bwiyongereye|\bwagabanutse|\bwahindutse|\byahindutse/,
    yieldw: /\byield|\bharvest|\bproduc|\bkg\b|\bkg\/ha|\bumusaruro|\bwera\b|\bangahe/,
    national: /\brwanda\b|\bnational|\bcountry|\ball districts|\bigihugu|\bmu gihugu|\buturere twose/,
    input: /\binput|\binyongeramusaruro/
  };
  function parse(q) {
    const t = norm(q);
    const district = DISTRICTS.find(d => new RegExp("\\b" + d.toLowerCase() + "\\b").test(t)) || null;
    const crop = (CROP_WORDS.find(([, re]) => re.test(t)) || [null])[0];
    const lever = (LEVER_WORDS.find(([, re]) => re.test(t)) || [null])[0];
    const sm = t.match(/\b(?:season|igihembwe)\s*(?:cya\s*)?([ab])\b/) || t.match(/\b20\d\d\s?([ab])\b/);
    const years = [...t.matchAll(/\b(20[12]\d)(?=[ab]?\b)/g)].map(m => +m[1]);
    return { t, district, crop, lever, season: sm ? sm[1].toUpperCase() : null, years, national: has(t, RE.national) };
  }
  function intentOf(p) {
    const t = p.t;
    if (has(t, RE.team)) return "team";
    if (has(t, RE.howto)) return "howto";
    if (has(t, RE.limits)) return "limits";
    if (has(t, RE.accuracy)) return "accuracy";
    if (has(t, RE.method)) return "method";
    if (has(t, RE.data) && !p.district) return "data";
    if (has(t, RE.targets) && !p.district) return "targets";
    if (has(t, RE.drivers)) return "drivers";
    if (has(t, RE.top) && !p.district) return "top";
    if (p.lever && has(t, RE.adopt) && !has(t, /what if|\bwould\b|\bif farmers|\bbakoresheje|\bbatangiye/)) return "adoption";
    if (!p.lever && has(t, RE.input) && has(t, RE.adopt)) return "adoption";
    if (p.lever && (has(t, RE.effect) || has(t, RE.rec))) return "effect";
    if (has(t, RE.rec)) return "rec";
    if (has(t, RE.trend)) return "trend";
    if (p.lever) return "effect";
    if (has(t, RE.yieldw) || p.district || p.crop) return "yield";
    return null;
  }

  /* ---------------------------------------------------------------- answers (numbers only from window.DASH) */
  const lv = l => tr("lv_" + l).toLowerCase();
  const C = c => esc(cropName(c));
  const latestYear = (crop, season) => Math.max(...trendRows(crop, season).map(r => r.year));
  function answer(q) {
    const p = parse(q), intent = intentOf(p);
    const crop = p.crop || S.crop, season = p.season || S.season, d = p.district || S.district;
    const go = (tab, extra) => ({ tab, crop, season, district: d, ...extra });
    const sn = seasonShort(season);
    switch (intent) {
      case "team": return { text: tr("kb_team"), go: { tab: "about" }, page: true };
      case "howto": return { text: tr("kb_howto"), go: { tab: "trends" }, page: true };
      case "limits": return { text: tr("kb_limits"), go: { tab: "about" }, page: true };
      case "method": return { text: tr("kb_method"), go: { tab: "about" }, page: true };
      case "data": return { text: tr("kb_data"), go: { tab: "about" }, page: true };
      case "accuracy": {
        const dv = VAL.find(v => v.validation.startsWith("district"));
        const w = WF.slice().sort((a, c) => a["MAPE_%"] - c["MAPE_%"]);
        const bb = w.find(x => ["last_year", "district_history"].includes(x.model)), bm = w.find(x => !["last_year", "district_history", "national_mean"].includes(x.model));
        if (!dv || !bb || !bm) return { text: tr("noData") };
        return { text: tr("as_acc", { e: nf(100 * dv.district_MAPE_model), b: nf(100 * dv.district_MAPE_baseline), wf: nf(bb["MAPE_%"]), wm: nf(bm["MAPE_%"]) }), go: { tab: "model" }, page: true };
      }
      case "targets": {
        let text = "";
        if (p.crop || TARGETS[crop]) {
          const t = TARGETS[crop];
          if (t) {
            const y = latestYear(crop, season), nat = natSeries(crop, season).find(n => n.year === y);
            text = nat ? tr("as_tgt_crop", { crop: C(crop), t: nf(t), season: sn, y, v: nf(nat.mean), p: nf(100 * nat.mean / t) }) + " " : "";
          } else text = tr("as_tgt_none", { crop: C(crop) }) + " ";
        }
        return { text: text + tr("kb_targets"), go: go("trends") };
      }
      case "drivers": {
        const rows = DRVC.filter(r => r.crop === crop);
        if (!rows.length) return { text: tr("noData") };
        const g = groupShares(rows), top = rows.slice().sort((a, c) => c.share_pct - a.share_pct).slice(0, 3).map(r => `${esc(featName(r.feature)).toLowerCase()} (${pct(r.share_pct, 1)})`);
        return { text: tr("as_drv", { crop: C(crop), mg: nf(g.g_mgmt), w: nf(g.g_weather), p: nf(g.g_plot), s: nf(g.g_soil), top: top.join(", ") }), go: go("drivers"), page: true };
      }
      case "top": {
        if (p.lever) {
          if (!leverAvailable(p.lever, crop)) return { text: tr("as_notscored", { lever: tr("lv_" + p.lever), crop: C(crop) }) };
          const rows = SCEN.filter(x => x.crop === crop && x.season === season && x.scenario === p.lever && x.plots >= 20 && x.extra_production_t > 0.5).sort((a, c) => c.extra_production_t - a.extra_production_t).slice(0, 5);
          if (!rows.length) return { text: tr("noData") };
          return { text: tr("as_top_lever", { lever: lv(p.lever), crop: C(crop), season: sn, list: rows.map(x => `${x.district} (${nf(x.extra_production_t)} t, +${nf(x.yield_gain_pct, 1)}%)`).join(", ") }), go: go("actions", { district: rows[0].district, lever: p.lever }) };
        }
        if (has(p.t, RE.topGain)) {
          const R = recsAll(crop, season), ds = DISTRICTS.filter(x => R[x].best).sort((a, c) => R[c].best.extra_production_t - R[a].best.extra_production_t).slice(0, 5);
          if (!ds.length) return { text: tr("noData") };
          return { text: tr("as_top_best", { crop: C(crop), season: sn, list: ds.map(x => `${x} (${nf(R[x].best.extra_production_t)} t, ${tr("lv_short_" + R[x].best.scenario).toLowerCase()})`).join(", ") }), go: go("actions", { district: ds[0], lever: "best" }) };
        }
        const y = p.years[0] || latestYear(crop, season);
        const rows = trendRows(crop, season).filter(r => r.year === y).sort((a, c) => c.yield_kg_ha - a.yield_kg_ha).slice(0, 5);
        if (!rows.length) return { text: tr("noData") };
        return { text: tr("as_top_yield", { crop: C(crop), season: sn, y, list: rows.map(r => `${r.district} (${nf(r.yield_kg_ha)} kg/ha)`).join(", ") }), go: go("trends", { district: rows[0].district }) };
      }
      case "adoption": {
        const ad = ADOPT.filter(r => r.crop === crop && r.season === season), ay = p.years.find(y => ad.some(r => r.year === y)) || Math.max(...ad.map(r => r.year));
        const da = ad.find(r => r.district === d && r.year === ay), na = ad.find(r => r.district === "Rwanda" && r.year === ay);
        if (p.lever && p.lever !== "package_fert_seed_manure") {
          const k = ADOPT_COL[p.lever];
          if (!da || !na || da[k] == null) return { text: tr("as_adopt_none", { lever: lv(p.lever), crop: C(crop), d, season: sn }) };
          return { text: tr("as_adopt", { d, lever: lv(p.lever), v: nf(100 * da[k]), crop: C(crop), season: sn, y: ay, nv: nf(100 * na[k]) }), go: go("trends") };
        }
        if (!da || !na) return { text: tr("as_adopt_none", { lever: tr("lever").toLowerCase(), crop: C(crop), d, season: sn }) };
        return { text: tr("as_adopt_all", { d, crop: C(crop), season: sn, y: ay, f: nf(100 * da.fert), s: nf(100 * da.seed), m: nf(100 * da.manure), nf: nf(100 * na.fert), ns: nf(100 * na.seed), nm: nf(100 * na.manure) }), go: go("trends") };
      }
      case "effect": {
        const l = p.lever;
        if (!leverAvailable(l, crop)) return { text: tr("as_notscored", { lever: tr("lv_" + l), crop: C(crop) }) };
        const n = SNAT.find(x => x.crop === crop && x.season === season && x.scenario === l);
        const x = SCEN.find(y => y.crop === crop && y.season === season && y.scenario === l && y.district === d && y.plots >= 20);
        if (!n) return { text: tr("noData") };
        if (x && !(p.national && !p.district)) return { text: tr("as_eff", { d, lever: lv(l), crop: C(crop), g: nf(x.yield_gain_pct, 1), t: nf(x.extra_production_t), season: sn, a: nf(x.adoption_pct), ng: nf(n.yield_gain_pct, 1), nt: nf(n.extra_production_t) }), go: go("actions", { lever: l }) };
        return { text: tr("as_eff_nat", { lever: lv(l), crop: C(crop), season: sn, ng: nf(n.yield_gain_pct, 1), nt: nf(n.extra_production_t) }) + (x || p.national ? "" : tr("as_eff_nod", { d })), go: go("actions", { lever: l }) };
      }
      case "rec": {
        const r = recFor(d, crop, season);
        if (!r.any) return { text: tr("as_rec_nodata", { crop: C(crop), d, season: sn }) };
        if (!r.best) return { text: tr("as_rec_none", { crop: C(crop), d, season: sn }), go: go("actions", { lever: "best" }) };
        const b = r.best;
        let text = tr("as_rec", { crop: C(crop), d, season: sn, lever: lv(b.scenario), g: nf(b.yield_gain_pct, 1), t: nf(b.extra_production_t), a: nf(b.adoption_pct) });
        if (r.next) text += tr("as_rec_next", { lever: lv(r.next.scenario), g: nf(r.next.yield_gain_pct, 1), t: nf(r.next.extra_production_t) });
        return { text, go: go("actions", { lever: "best" }) };
      }
      case "trend": {
        const base = p.years[0] || S.base;
        const nat = natSeries(crop, season), nb = baseVal(nat.map(n => ({ year: n.year, yield_kg_ha: n.mean })), base), nl = nat.at(-1);
        const ch = (a, b) => signPct(100 * (b / a - 1));
        if (p.national && !p.district) {
          if (!nb || !nl) return { text: tr("noData") };
          const up = DISTRICTS.map(x => { const rr = seriesFor(crop, season, x), bb = baseVal(rr, base), ll = rr.at(-1); return bb && ll && ll.year > bb.year ? [x, 100 * (ll.yield_kg_ha / bb.yield_kg_ha - 1)] : null; }).filter(Boolean).sort((a, c) => c[1] - a[1]).slice(0, 3);
          return { text: tr("as_trend_nat", { crop: C(crop), season: sn, b: nf(nb.yield_kg_ha), by: nb.year, l: nf(nl.mean), ly: nl.year, c: ch(nb.yield_kg_ha, nl.mean), up: up.map(([x, v]) => `${x} (${signPct(v)})`).join(", ") }), go: go("trends", { base: nb.year }) };
        }
        const rows = seriesFor(crop, season, d), b = baseVal(rows, base), l = rows.at(-1);
        if (!b || !l || l.year <= b.year) return { text: tr("as_noyield", { crop: C(crop), d, season: sn, y: "" }) };
        return { text: tr("as_trend", { crop: C(crop), d, season: sn, b: nf(b.yield_kg_ha), by: b.year, l: nf(l.yield_kg_ha), ly: l.year, c: ch(b.yield_kg_ha, l.yield_kg_ha), nc: nb && nl ? ch(nb.yield_kg_ha, nl.mean) : "–" }), go: go("trends", { base: YEARS.includes(b.year) && b.year < YEARS.at(-1) ? b.year : S.base }) };
      }
      case "yield": {
        const y = p.years[0] || null, t = TARGETS[crop];
        if (p.national && !p.district) {
          const yy = y || latestYear(crop, season), rows = trendRows(crop, season).filter(r => r.year === yy).sort((a, c) => c.yield_kg_ha - a.yield_kg_ha);
          if (!rows.length) return { text: tr("noData") };
          const m = mean(rows.map(r => r.yield_kg_ha));
          return { text: tr("as_yield_nat", { season: sn, y: yy, crop: C(crop), n: rows.length, v: nf(m), hi: `${rows[0].district} (${nf(rows[0].yield_kg_ha)})`, lo: `${rows.at(-1).district} (${nf(rows.at(-1).yield_kg_ha)})`, tgt: t ? tr("as_tgt_nat", { t: nf(t) }) : "" }), go: go("trends") };
        }
        const rows = seriesFor(crop, season, d), r = y ? rows.find(x => x.year === y) : rows.at(-1);
        if (!r) return { text: tr("as_noyield", { crop: C(crop), d, season: sn, y: y ? " " + y : "" }) };
        const peers = trendRows(crop, season).filter(x => x.year === r.year).sort((a, c) => c.yield_kg_ha - a.yield_kg_ha);
        return { text: tr("as_yield", { crop: C(crop), d, season: sn, y: r.year, v: nf(r.yield_kg_ha), rank: ord(peers.findIndex(x => x.district === d) + 1), n: peers.length, tgt: t ? tr("as_tgt", { p: nf(100 * r.yield_kg_ha / t), t: nf(t) }) : "" }), go: go("trends") };
      }
      default: return { text: tr("as_unknown"), suggest: suggestions().slice(0, 3) };
    }
  }
  function suggestions() {
    const v = { d: S.district, crop: cropName(S.crop) };
    return ["as_q1", "as_q2", "as_q3", "as_q4", "as_q5", "as_q6"].map(k => tr(k, v));
  }

  /* ---------------------------------------------------------------- user interface */
  const root = document.createElement("div");
  root.innerHTML = `
    <button type="button" id="ask-btn" aria-expanded="false" aria-controls="ask-panel"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg><span id="ask-btn-t"></span></button>
    <div id="ask-panel" role="dialog" aria-labelledby="ask-title" hidden>
      <div class="ask-head"><b id="ask-title"></b><button type="button" id="ask-close" aria-label="Close">×</button></div>
      <div id="ask-log" aria-live="polite"></div>
      <div id="ask-chips"></div>
      <form id="ask-form" autocomplete="off"><input id="ask-in" type="text" maxlength="300"><button type="submit" id="ask-send"></button></form>
    </div>`;
  document.body.appendChild(root);
  const $ = id => document.getElementById(id);
  const btn = $("ask-btn"), panel = $("ask-panel"), log = $("ask-log"), input = $("ask-in");

  function add(who, html) {
    const m = document.createElement("div");
    m.className = "ask-msg " + who; m.innerHTML = html;
    log.appendChild(m); log.scrollTop = log.scrollHeight;
    return m;
  }
  function chip(q) { return `<button type="button" class="ask-chip" data-q="${esc(q)}">${esc(q)}</button>`; }
  function ask(q) {
    q = q.trim(); if (!q) return;
    add("me", esc(q));
    const a = answer(q);
    let html = `<p>${a.text}</p>`;
    if (a.suggest) html += `<div class="ask-sugg">${a.suggest.map(chip).join("")}</div>`;
    if (a.go) html += `<button type="button" class="ask-go">${tr(a.page ? "as_open_page" : "as_open")} →</button>`;
    const m = add("bot", html);
    if (a.go) m.querySelector(".ask-go").addEventListener("click", () => goTo(a.go));
    m.querySelectorAll(".ask-chip").forEach(c => c.addEventListener("click", () => ask(c.dataset.q)));
    return a;
  }
  function goTo(g) {
    ["crop", "season", "district", "lever", "base"].forEach(k => { if (g[k] != null) S[k] = g[k]; });
    fillControls();
    if (matchMedia("(max-width: 640px)").matches) close();
    if (location.hash.replace("#", "") !== g.tab) location.hash = g.tab; else render();
  }
  function refresh() {
    $("ask-btn-t").textContent = tr("as_btn"); $("ask-title").textContent = tr("as_title");
    $("ask-close").setAttribute("aria-label", tr("as_close")); $("ask-send").textContent = tr("as_send");
    input.placeholder = tr("as_ph"); input.setAttribute("aria-label", tr("as_ph"));
    $("ask-chips").innerHTML = suggestions().map(chip).join("");
    $("ask-chips").querySelectorAll(".ask-chip").forEach(c => c.addEventListener("click", () => ask(c.dataset.q)));
  }
  function open() {
    panel.hidden = false; btn.setAttribute("aria-expanded", "true");
    if (!log.children.length) add("bot", `<p>${tr("as_hello")}</p>`);
    input.focus();
  }
  function close() { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); btn.focus(); }
  btn.addEventListener("click", () => (panel.hidden ? open() : close()));
  $("ask-close").addEventListener("click", close);
  panel.addEventListener("keydown", e => { if (e.key === "Escape") close(); });
  $("ask-form").addEventListener("submit", e => { e.preventDefault(); ask(input.value); input.value = ""; });
  refresh();
  return { refresh, answer, ask, parse, intentOf, open, close };
})();
