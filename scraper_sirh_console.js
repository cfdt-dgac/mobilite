/**
 * CFDT — Scraper SIRH Aviation Civile (v4)
 * Coller dans la console (F12 → Console) sur une FICHE DÉTAIL déjà ouverte.
 * Contexte console : sélectionner "top" dans le menu déroulant.
 *
 * Stratégie v4 : navigation via bouton "Suivant" sur les fiches détail
 *   1. Ouvrir manuellement la 1ère fiche (clic sur loupe du 1er résultat)
 *   2. Coller ce script → il extrait puis clique "Suivant" jusqu'à la fin
 *   3. Un fichier offres_sirh.json est téléchargé automatiquement
 *
 * Champs extraits par fiche :
 *   Identification (N° AVE, libellé, GS, poste, UO, emploi, filière, métier,
 *   type de poste, personne remplacée, nb postes, vacance)
 *   + Corps / restrictions de grade
 *   + Définition, Tâches, Commentaires, Profil-Qualification (texte libre)
 *   + Responsable à contacter (nom, tél, email)
 */
(async function () {

  // ── Réglages ─────────────────────────────────────────────────────────────
  const DELAI   = 1500;   // ms d'attente entre chaque fiche
  const TIMEOUT = 30000;  // ms max pour chargement fiche suivante
  const MAX     = 0;      // 0 = tout scraper / N = s'arrêter après N fiches (test)

  // ── Utilitaires ──────────────────────────────────────────────────────────
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  function doc() {
    try { if (window.frames && window.frames[0] && window.frames[0].document) return window.frames[0].document; } catch (_) {}
    return window.document;
  }

  function txt(el) {
    return el ? el.innerText.replace(/\s+/g, ' ').trim() : '';
  }

  function normKey(s) {
    return (s || '').toLowerCase()
      .replace(/[éèëê]/g, 'e').replace(/[àâä]/g, 'a').replace(/[ùûü]/g, 'u')
      .replace(/[ôö]/g, 'o').replace(/[îï]/g, 'i').replace(/[ç]/g, 'c')
      .replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').substring(0, 55);
  }

  // ── Lecture N° AVE sur la fiche courante ─────────────────────────────────
  // Structure réelle : td "N° de l'AVE 126733" (parent) ou td "N° de l'AVE"
  // suivi 2 positions plus loin de td "126733"
  function getCurrentAve() {
    const d = doc();
    const tds = Array.from(d.querySelectorAll('td'));
    // Pattern : ancien format 4-7 chiffres (ex: 126700) OU nouveau format 2026-XXXXXXX
    const AVE_RE = /(\d{4}-\d{6,7}|\d{4,7})/;
    for (let i = 0; i < tds.length; i++) {
      const t = txt(tds[i]).trim();
      if (t.length > 40) continue;                          // ignorer les grands td composites
      if (!/N[°º]?\s*de\s*l.AVE/i.test(t)) continue;
      // Cas A : le numéro est dans ce même td (ex: "N° de l'AVE 126733" ou "N° de l'AVE 2026-1234567")
      const m = t.match(new RegExp(AVE_RE.source + '$'));
      if (m) return m[1];
      // Cas B : scanner les 6 td suivants
      for (let j = i + 1; j <= Math.min(i + 6, tds.length - 1); j++) {
        const v = txt(tds[j]).trim();
        if (AVE_RE.test(v) && v.match(new RegExp('^' + AVE_RE.source + '$'))) return v;
      }
    }
    return '';
  }

  // ── Attente du chargement de la fiche suivante ────────────────────────────
  async function waitNextDetail(prevAve) {
    const start = Date.now();
    while (Date.now() - start < TIMEOUT) {
      await sleep(400);
      try {
        const cur = getCurrentAve();
        if (cur && cur !== prevAve) return cur;
      } catch (_) {}
    }
    console.warn('  ⚠ Timeout — fiche suivante non détectée');
    return null;
  }

  // ── Clic sur le bouton Suivant ────────────────────────────────────────────
  function clickSuivant() {
    const d = doc();
    for (const el of d.querySelectorAll('a, button, input[type="button"], input[type="submit"], [onclick]')) {
      const t = (el.innerText || el.value || '').trim();
      if (t === 'Suivant' || t.toLowerCase() === 'suivant') {
        el.click();
        return true;
      }
    }
    return false;
  }

  // ── Extraction complète d'une fiche ──────────────────────────────────────
  function extractAll() {
    const d = doc();
    const row = {};

    // ── 1. Corps / restrictions via data-label (seuls champs avec data-label) ──
    const corpsList = [];
    d.querySelectorAll('[data-label="Corps"]').forEach(el => {
      const v = txt(el.querySelector('.HRTEXT_TXTR1') || el).trim();
      if (v && !v.toLowerCase().includes('corps') && !corpsList.includes(v)) corpsList.push(v);
    });
    const restrList = [];
    d.querySelectorAll('[data-label="Restriction grade"]').forEach(el => {
      const v = txt(el.querySelector('.HRTEXT_TXTR1') || el).trim();
      if (v) restrList.push(v);
    });
    if (corpsList.length) row['corps_liste'] = corpsList.join(' / ');
    if (restrList.length)  row['restrictions_grades'] = restrList.join(' | ');

    // ── 2. Paires label/valeur via TR directs ───────────────────────────────
    // Chaque ligne de formulaire = <tr> avec td-enfants directs [label, spacer?, valeur]
    // On utilise :scope > td pour éviter de traverser les tables imbriquées
    const allTds = Array.from(d.querySelectorAll('td'));
    for (const tr of d.querySelectorAll('tr')) {
      if (tr.closest('.gp-navigation, .hrportal-header-links, [class*="navigation"]')) continue;
      // Enfants directs td uniquement (pas les td des sous-tables)
      const direct = Array.from(tr.querySelectorAll(':scope > td'));
      const nonEmpty = direct.filter(td => txt(td).trim().length > 0);
      if (nonEmpty.length !== 2) continue;           // exactement 2 cellules non vides
      const lbl = txt(nonEmpty[0]).trim();
      const val = txt(nonEmpty[1]).trim();
      if (!lbl || !val || lbl === val) continue;
      if (lbl.length > 60) continue;
      if (/function\s*\(|var\s+/.test(lbl)) continue;
      if (val.startsWith(lbl)) continue;
      const key = normKey(lbl);
      if (key && !row[key]) row[key] = val;
    }

    // ── 3. Sections texte libre ──────────────────────────────────────────────
    // Structure : td "Définition Chef de programme..." → extraire après le titre
    // ou td "Tâches Il élabore..." etc.
    const SECTIONS = [
      ['Définition',              'definition'],
      ['Tâches',                  'taches'],
      ['Commentaires sur le poste', 'commentaires'],
      ['Profil - Qualification',  'profil_qualification'],
    ];
    for (const td of allTds) {
      const t = txt(td).trim();
      if (t.length < 25) continue;
      for (const [titre, key] of SECTIONS) {
        if (!row[key] && t.startsWith(titre + ' ') && t.length > titre.length + 15) {
          row[key] = t.substring(titre.length + 1).trim();
          break;
        }
      }
    }

    return row;
  }

  // ── Boucle principale ─────────────────────────────────────────────────────
  console.log('══════════════════════════════════════════════════════');
  console.log(' CFDT Scraper SIRH v4 — Navigation via Suivant');
  console.log(' Assurez-vous d\'être sur la 1ère fiche détail');
  console.log('══════════════════════════════════════════════════════');

  const allRows = [];
  const seenAves = new Set();

  while (true) {
    if (MAX > 0 && allRows.length >= MAX) {
      console.log('  → Limite de test atteinte (' + MAX + ' fiches).');
      break;
    }

    const ave = getCurrentAve();
    if (!ave) {
      console.warn('  ⚠ N° AVE illisible. Êtes-vous bien sur une fiche détail ?');
      break;
    }
    if (seenAves.has(ave)) {
      console.log('  → AVE ' + ave + ' déjà vu — fin de liste.');
      break;
    }
    seenAves.add(ave);

    const row = extractAll();
    allRows.push(row);

    if (allRows.length <= 5 || allRows.length % 20 === 0)
      console.log('  ' + allRows.length + ' fiches — AVE courant : ' + ave);

    // Clic Suivant
    const hasSuivant = clickSuivant();
    if (!hasSuivant) {
      console.log('  → Bouton Suivant absent — fin de liste (' + allRows.length + ' fiches).');
      break;
    }

    const nextAve = await waitNextDetail(ave);
    if (!nextAve) break;
    await sleep(DELAI);
  }

  // ── Téléchargement JSON ───────────────────────────────────────────────────
  console.log('\nTéléchargement du fichier JSON…');
  const json = JSON.stringify(allRows, null, 2);
  const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'offres_sirh.json';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  console.log('');
  console.log('══════════════════════════════════════════════════════');
  console.log(' ✔ offres_sirh.json téléchargé — ' + allRows.length + ' fiches');
  console.log('   Transférez sur votre PC principal puis importez');
  console.log('   via l\'appli Flask → Étape 2 → Import SIRH.');
  console.log('══════════════════════════════════════════════════════');

})();
