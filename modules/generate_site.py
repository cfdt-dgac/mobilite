#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_site.py
Génère le dossier site/ statique (HTML + JSON) prêt à déployer sur Netlify.
"""

import json
import re
import shutil
from html import escape as _html_escape
from pathlib import Path
import pandas as pd


# ── Utilitaires ───────────────────────────────────────────────────────────────

def _e(v) -> str:
    """Échappe une valeur pour l'insérer sans risque dans du HTML (anti-XSS)."""
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return _html_escape(str(v), quote=True)


_ROBOTS_META = '<meta name="robots" content="noindex, nofollow, noarchive">'


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Pages HTML : interdire l'indexation par les moteurs de recherche
    if path.suffix == ".html" and _ROBOTS_META not in content:
        content = content.replace('<meta charset="utf-8">',
                                  '<meta charset="utf-8">\n' + _ROBOTS_META, 1)
    path.write_text(content, encoding="utf-8")


# En-têtes HTTP appliqués par Netlify à tout le site (fichier _headers)
_NETLIFY_HEADERS = """/*
  X-Robots-Tag: noindex, nofollow, noarchive
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()
  Strict-Transport-Security: max-age=31536000
  Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'; frame-ancestors 'none'
"""


def _write_json(data, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _records(df: pd.DataFrame) -> list[dict]:
    return [
        {k: ("" if pd.isna(v) else str(v)) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]


# ── Page d'accueil ────────────────────────────────────────────────────────────

def _render_home(campaign: str, has_resultats: bool) -> str:
    resultats_link = ""
    if has_resultats:
        resultats_link = """
    <li><a href="resultats.html">Résultats de la CDM</a>
      — agents retenus par Grand service et par corps, postes vacants</li>"""

    return f"""<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CFDT Aviation Civile — Mobilité {campaign}</title>
<link rel="stylesheet" href="assets/styles.css">
{_NAV_CSS}
</head><body>
{_CFDT_BANNER}
{_nav("index.html", has_resultats)}
<main class="container">
  <h1>Espace Mobilité CFDT</h1>
  <p>Campagne : <strong>{campaign}</strong></p>
  <ul>
    <li><a href="tableau.html">Tableau des postes ouverts (filtrable)</a>
      — avec lien vers la fiche officielle CSP pour chaque poste</li>
    <li><a href="offres.html">Fiches détaillées des offres</a>
      — description complète, missions, profil, contacts</li>
    <li><a href="info.html">Informations pratiques</a>
      — modalités de candidature, contacts DSNA/SDRH</li>{resultats_link}
  </ul>
  <p class="small">Espace CFDT Aviation Civile. Contact&nbsp;:
    <code>cfdt-dgac@regis-dgac.net</code></p>
</main>
<footer>© CFDT Aviation Civile</footer>
</body></html>"""


# ── Bandeau CFDT + Navigation commune ────────────────────────────────────────

_CFDT_BANNER = """<header class="cb-header" role="banner">
  <ul class="cb-toolbar">
    <li><a href="https://www.cfdt.fr/" class="cb-link">CFDT.fr</a></li>
    <li><a href="https://www.syndicalismehebdo.fr/" class="cb-link" target="_blank" rel="noopener">Syndicalisme Hebdo</a></li>
    <li><a href="https://www.cfdtdgac.fr/contact" class="cb-link">Nous contacter</a></li>
    <li><a href="https://monespace.cfdt.fr" class="cb-pill cb-pill--peach" target="_blank" rel="noopener"><span>Espace adhérent·e</span><svg aria-hidden="true" viewBox="0 0 16 16" width="16" height="16"><path d="M13.3 14v-1.3a2.7 2.7 0 0 0-2.6-2.7H5.3a2.7 2.7 0 0 0-2.6 2.7V14M10.7 4.7a2.7 2.7 0 1 1-5.4 0 2.7 2.7 0 0 1 5.4 0Z" stroke="currentColor" stroke-width="1.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg></a></li>
  </ul>
  <div class="cb-wrapper">
    <a href="https://www.cfdtdgac.fr/" class="cb-logo" aria-label="CFDT Aviation Civile — accueil">
      <svg class="cb-logo-svg" width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="CFDT" role="img">
      <path d="M48 24C48 37.2548 37.2548 48 24 48C10.7452 48 0 37.2548 0 24C0 10.7452 10.7452 0 24 0C37.2548 0 48 10.7452 48 24Z" fill="#E7591C"/>
      <path d="M15.909 25.6449C15.2472 28.0587 13.2209 29.7477 10.6905 29.994C8.81721 30.1763 6.98829 29.5433 5.73143 28.2775C4.85881 27.3988 4.2941 26.316 4.03729 25.0291C3.94915 24.588 3.94947 23.4659 4.03793 22.9945C4.50299 20.5153 6.31658 18.6196 8.68753 18.1347C9.81504 17.9041 10.8624 17.9543 11.9084 18.2887C13.5045 18.7991 14.831 19.9691 15.5592 21.5096C15.7276 21.8651 15.9122 22.3886 15.9483 22.6131L15.9687 22.7402H13.043L13.0065 22.647C12.5843 21.5648 11.7976 20.8043 10.8234 20.537C10.4778 20.4421 9.85656 20.4089 9.50042 20.4664C8.4911 20.6293 7.65649 21.263 7.1761 22.2314C6.23673 24.1242 6.95252 26.5019 8.71277 27.3355C9.36755 27.6457 10.2306 27.7057 10.9253 27.4885C11.8634 27.1956 12.6102 26.4757 12.9877 25.5006L13.0653 25.3003L14.5298 25.2913C15.3353 25.2865 15.9943 25.2942 15.9943 25.3083C15.9943 25.3223 15.9559 25.474 15.909 25.6449Z" fill="white"/>
      <path d="M29.3451 29.1708C29.0577 29.4823 28.606 29.7257 28.0579 29.8643H28.0576C27.8356 29.9202 27.6484 29.9374 27.1665 29.9457C26.5203 29.9566 26.504 29.9556 26.0827 29.8726C25.4621 29.75 24.8778 29.4867 24.375 29.1028C23.8721 28.719 23.464 28.2248 23.1822 27.6585C23.0212 27.3365 22.8245 26.7066 22.758 26.3003C22.6315 25.5283 22.7021 24.4816 22.9299 23.7566C23.4307 22.1615 24.7872 21.0285 26.466 20.804C26.8662 20.7503 27.5951 20.7848 27.9634 20.8749C28.4083 20.9835 28.9027 21.24 29.1675 21.4997L29.3873 21.7149V17.9594H32.3031V29.8266H29.4889V29.0143L29.3451 29.1708ZM25.7224 26.3863C25.9917 26.9328 26.5002 27.3052 27.1329 27.4192C27.2255 27.4358 27.4258 27.4438 27.5775 27.4365C28.1333 27.41 28.5511 27.2375 28.897 26.8925C29.1382 26.652 29.2787 26.4195 29.408 26.0461C29.4895 25.8107 29.502 25.7235 29.5016 25.3849C29.5016 25.046 29.4895 24.9617 29.4096 24.741C29.2812 24.3871 29.1337 24.1562 28.8871 23.9249C28.6587 23.7103 28.3115 23.525 27.9966 23.4484C27.5747 23.3455 26.9665 23.412 26.5577 23.6055C25.594 24.061 25.2088 25.344 25.7224 26.3863Z" fill="white"/>
      <path d="M38.6772 27.6981V29.9282L38.1262 29.925C37.238 29.9195 36.7225 29.8173 36.1341 29.5295C35.8629 29.3967 35.7636 29.3235 35.5049 29.0651C35.2474 28.8086 35.174 28.7096 35.0529 28.4573C34.7444 27.8137 34.7102 27.493 34.7102 25.2457V23.5202H33.76L33.7775 21.2655L34.7096 21.2464L34.7271 17.9763H37.6433L37.6609 21.2467L38.1604 21.2556L38.6603 21.2652V23.5027L37.6602 23.5215L37.6609 25.3939C37.6615 27.1583 37.665 27.2745 37.7257 27.4077C37.825 27.6265 37.9193 27.67 38.3271 27.685L38.6772 27.6981Z" fill="white"/>
      <path d="M20.8087 23.5202V29.8269H17.9267V23.5222L16.994 23.5033V21.2655L17.9267 21.2467V20.9337C17.928 19.7161 18.2822 18.9441 19.0593 18.4656C19.579 18.1453 20.1644 18.0118 21.2156 17.9728L21.8595 17.9491V20.2249L21.5059 20.2364C21.2134 20.246 21.1364 20.2601 21.0588 20.3182C20.8627 20.4648 20.8288 20.5462 20.8141 20.9104L20.8007 21.2483H21.8595V23.5202H20.8087Z" fill="white"/>
      <path d="M44.0512 26.9954L44.0694 29.8266H41.1181L41.1357 26.9954H44.0512Z" fill="white"/>
      <path d="M44.0691 21.2483L44.0512 24.0795L43.3901 24.0805C43.0266 24.0811 42.3667 24.077 41.9237 24.0715L41.1184 24.0613V21.2483H44.0691Z" fill="white"/>
    </svg>
      <span class="cb-tagline">Aviation civile</span>
    </a>
    <nav class="cb-menu" aria-label="Menu principal">
      <ul class="cb-list">
        <li class="cb-item cb-has-sub"><button type="button" class="cb-link cb-link--primary" aria-expanded="false" aria-controls="cb-sub-0">Connaître mes droits <svg aria-hidden="true" class="cb-arrow" viewBox="0 0 16 16"><path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg></button><div class="cb-sub" id="cb-sub-0"><p class="cb-sub-title">Connaître mes droits</p><p class="cb-sub-text">Des fiches pratiques, vos droits dans la fonction publique et à la DGAC</p><ul><li><a href="https://www.cfdtdgac.fr/mes-droits/fiches-droits?t%5B%5D=remuneration">Rémunération</a></li><li><a href="https://www.cfdtdgac.fr/mes-droits/fiches-droits?t%5B%5D=recrutement">Recrutement</a></li><li><a href="https://www.cfdtdgac.fr/mes-droits/fiches-droits?t%5B%5D=mobilite">Mobilité</a></li><li><a href="https://www.cfdtdgac.fr/mes-droits/fiches-droits?t%5B%5D=promotion-avancement">Promotion &amp; Avancement</a></li><li><a href="https://www.cfdtdgac.fr/mes-droits/fiches-droits?t%5B%5D=emplois-fonctionnels">Emplois fonctionnels</a></li><li><a href="https://www.cfdtdgac.fr/mes-droits/fiches-droits?t%5B%5D=organisation-du-travail">Organisation du travail</a></li><li><a href="https://www.cfdtdgac.fr/mes-droits/fiches-droits?t%5B%5D=conges-absences">Congés &amp; Absences</a></li><li><a href="https://www.cfdtdgac.fr/mes-droits/fiches-droits?t%5B%5D=formation-professionnelle">Formation professionnelle</a></li><li><a href="https://www.cfdtdgac.fr/mes-droits/fiches-droits?t%5B%5D=sante-securite-et-conditions-de-travail">Santé, sécurité et conditions de travail</a></li><li><a href="https://www.cfdtdgac.fr/mes-droits/fiches-droits?t%5B%5D=tseeac-1&amp;t%5B%5D=icna&amp;t%5B%5D=ieeac&amp;t%5B%5D=iessa">Corps techniques</a></li><li><a href="https://www.cfdtdgac.fr/mes-droits/fiches-droits?t%5B%5D=attache&amp;t%5B%5D=assistant-adjoint">Administratifs</a></li><li><a href="https://www.cfdtdgac.fr/mes-droits/fiches-droits?t%5B%5D=personnels-medico-sociaux-1">Personnels médico-sociaux</a></li><li><a href="https://www.cfdtdgac.fr/mes-droits/fiches-droits?t%5B%5D=contractuels">Contractuels</a></li><li><a href="https://www.cfdtdgac.fr/mes-droits/fiches-droits?t%5B%5D=ouvrier-d-etat-opa-1&amp;t%5B%5D=itpe-tsdd-isic-1&amp;t%5B%5D=ipef-adm-civil">Autres corps</a></li></ul></div></li><li class="cb-item cb-has-sub"><button type="button" class="cb-link cb-link--primary" aria-expanded="false" aria-controls="cb-sub-1">S'informer <svg aria-hidden="true" class="cb-arrow" viewBox="0 0 16 16"><path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg></button><div class="cb-sub" id="cb-sub-1"><p class="cb-sub-title">S'informer</p><p class="cb-sub-text">L'actualité de la CFDT Aviation Civile, nationale et près de chez vous</p><ul><li><a href="https://www.cfdtdgac.fr/sinformer/actualites-nationales">Actualités nationales</a></li><li><a href="https://www.cfdtdgac.fr/sinformer/actualites-locales">Actualités locales</a></li><li><a href="https://www.cfdt.fr/">Publications confédérales</a></li><li><a href="https://uffa.cfdt.fr/">Publications CFDT Fonctions publiques</a></li></ul></div></li><li class="cb-item"><a href="index.html" class="cb-link cb-link--primary" aria-current="true">Espace mobilité</a></li><li class="cb-item cb-has-sub"><button type="button" class="cb-link cb-link--primary" aria-expanded="false" aria-controls="cb-sub-3">Votre syndicat <svg aria-hidden="true" class="cb-arrow" viewBox="0 0 16 16"><path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg></button><div class="cb-sub" id="cb-sub-3"><p class="cb-sub-title">Votre syndicat</p><p class="cb-sub-text">Qui sommes-nous, vos représentants, nos permanences</p><ul><li><a href="https://www.cfdtdgac.fr/qui-est-la-cfdt/votre-syndicat/nos-valeurs">Nos valeurs</a></li><li><a href="https://www.cfdtdgac.fr/qui-est-la-cfdt/votre-syndicat/nos-revendications">Nos revendications</a></li><li><a href="https://www.cfdtdgac.fr/qui-est-la-cfdt/votre-syndicat/vos-victoires">Vos victoires</a></li><li><a href="https://www.cfdtdgac.fr/qui-est-la-cfdt/votre-syndicat/histoire-de-la-cfdt-aviation-civile">Histoire de la CFDT Aviation Civile</a></li><li><a href="https://www.cfdtdgac.fr/qui-est-la-cfdt/votre-syndicat/l-equipe-nationale">L'équipe nationale</a></li><li><a href="https://www.cfdtdgac.fr/qui-est-la-cfdt/votre-syndicat/vos-representants-par-instance">Vos représentants par instance</a></li><li><a href="https://www.cfdtdgac.fr/qui-est-la-cfdt/votre-syndicat/nos-permanences-nationales">Nos permanences nationales</a></li><li><a href="https://www.cfdtdgac.fr/qui-est-la-cfdt/votre-syndicat/vos-sections-locales">Vos sections locales</a></li><li><a href="https://www.cfdtdgac.fr/qui-est-la-cfdt/votre-syndicat/assistance-juridique">Assistance juridique</a></li><li><a href="https://www.cfdtdgac.fr/qui-est-la-cfdt/votre-syndicat/greve-indemnisation">Grève &amp; indemnisation</a></li><li><a href="https://www.cfdtdgac.fr/qui-est-la-cfdt/votre-syndicat/formations-syndicales">Formations syndicales</a></li></ul></div></li>
      </ul>
      <div class="cb-mobile-extra">
        <a href="https://monespace.cfdt.fr" class="cb-pill cb-pill--peach" target="_blank" rel="noopener"><span>Espace adhérent·e</span></a>
        <a href="https://www.cfdtdgac.fr/adherer" class="cb-pill cb-pill--orange"><span>Adhérer</span></a>
        <p><a href="https://www.cfdt.fr/">CFDT.fr</a> · <a href="https://www.syndicalismehebdo.fr/" target="_blank" rel="noopener">Syndicalisme Hebdo</a> · <a href="https://www.cfdtdgac.fr/contact">Nous contacter</a></p>
      </div>
    </nav>
    <a href="https://www.cfdtdgac.fr/resultats-de-recherche" class="cb-search" aria-label="Rechercher sur cfdtdgac.fr"><svg aria-hidden="true" viewBox="0 0 16 16" width="16" height="16"><circle cx="7" cy="7" r="4.5" stroke="currentColor" stroke-width="2" fill="none"/><path d="M10.5 10.5 14 14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></a>
    <button type="button" class="cb-toggle" aria-expanded="false" aria-label="Ouvrir le menu"><span class="cb-toggle-label">Menu</span><i class="cb-toggle-icon"></i></button>
    <a href="https://www.cfdtdgac.fr/adherer" class="cb-pill cb-pill--orange cb-join"><span>Adhérer</span><svg aria-hidden="true" viewBox="0 0 16 16" width="16" height="16"><path d="M3.3 8h9.4M12.7 8 8 3.3M12.7 8 8 12.7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg></a>
  </div>
</header>
<script>
(function(){
  var h=document.querySelector('.cb-header');if(!h)return;
  var t=h.querySelector('.cb-toggle');
  t.addEventListener('click',function(){var o=h.classList.toggle('cb-open');t.setAttribute('aria-expanded',o);t.querySelector('.cb-toggle-label').textContent=o?'Fermer':'Menu';});
  h.querySelectorAll('.cb-has-sub > button').forEach(function(b){
    b.addEventListener('click',function(){
      var o=b.getAttribute('aria-expanded')!=='true';
      h.querySelectorAll('.cb-has-sub > button').forEach(function(x){x.setAttribute('aria-expanded','false');});
      b.setAttribute('aria-expanded',o);
    });
  });
  document.addEventListener('click',function(e){if(!h.contains(e.target))h.querySelectorAll('.cb-has-sub > button').forEach(function(x){x.setAttribute('aria-expanded','false');});});
  document.addEventListener('keydown',function(e){if(e.key==='Escape')h.querySelectorAll('.cb-has-sub > button').forEach(function(x){x.setAttribute('aria-expanded','false');});});
})();
</script>
"""

_NAV_CSS = """
<style>
/* Bandeau CFDT Aviation Civile — reprise du bandeau de cfdtdgac.fr */
:root { --cb-orange:#E7591C; --cb-peach:#FBCBA7; --cb-ink:#222; --cb-spc-x:clamp(1rem,5vw,4rem); }
.cb-header { position:relative; z-index:999; background:#f9fafb; padding:.75rem var(--cb-spc-x) 1rem; color:var(--cb-ink); font-family:"Founders Grotesk","Helvetica Neue",Arial,sans-serif; font-size:16px; line-height:1.5; }
.cb-header ul { list-style:none; margin:0; padding:0; }
.cb-header a, .cb-header button { color:inherit; text-decoration:none; font:inherit; }
.cb-header button { background:none; border:0; padding:0; cursor:pointer; }
.cb-toolbar { display:flex; justify-content:center; align-items:center; gap:2rem; margin-bottom:.75rem !important; }
.cb-wrapper { display:grid; grid-template-columns:auto 1fr auto auto; align-items:center; gap:1rem; position:relative; z-index:1; max-width:1400px; margin:0 auto; }
.cb-wrapper::before { content:""; position:absolute; z-index:-1; width:100%; height:100%; grid-column:1 / -2; grid-row:1; border-radius:100vmax; background:#fff; box-shadow:0 0 .75rem rgba(0,0,0,.05); }
.cb-logo { display:flex; align-items:center; gap:.625rem; margin:.5rem 0 .5rem .5rem; }
.cb-logo-svg { display:block; width:48px; height:48px; flex-shrink:0; }
.cb-tagline { text-transform:uppercase; font-family:"Gotham Condensed","Arial Narrow","Roboto Condensed",sans-serif; font-stretch:condensed; font-size:1.3125rem; font-weight:500; line-height:1; color:var(--cb-orange); white-space:nowrap; }
.cb-link { display:inline-flex; align-items:center; gap:.25rem; font-weight:600; line-height:1.35;
  background-image:linear-gradient(var(--cb-orange),var(--cb-orange)); background-size:0% .1em; background-repeat:no-repeat; background-position:left bottom; transition:background-size .2s; }
.cb-link:hover, .cb-link[aria-current="true"], .cb-link[aria-expanded="true"] { background-size:100% .1em; }
.cb-link--primary { font-size:1.1875rem; }
.cb-arrow { width:1rem; height:1rem; margin-top:.125rem; transition:rotate .2s; }
[aria-expanded="true"] > .cb-arrow { rotate:-180deg; }
.cb-list { display:flex; justify-content:flex-end; align-items:center; gap:1.5rem; }
.cb-item { position:relative; }
.cb-sub { display:none; position:absolute; top:calc(100% + 1.4rem); left:50%; transform:translateX(-50%); width:min(560px,90vw); background:#fff; border-radius:1.25rem; box-shadow:0 8px 30px rgba(0,0,0,.12); padding:1.5rem 1.75rem; }
.cb-has-sub > button[aria-expanded="true"] + .cb-sub { display:block; }
.cb-sub-title { font-size:1.375rem; font-weight:600; margin:0 0 .25rem; }
.cb-sub-text { font-size:.9375rem; color:#555; margin:0 0 1rem; }
.cb-sub ul { columns:2; column-gap:1.5rem; }
.cb-sub li { break-inside:avoid; margin-bottom:.5rem; }
.cb-sub a { font-weight:600; font-size:.9375rem; }
.cb-sub a::before { content:"→ "; color:var(--cb-orange); }
.cb-sub a:hover { color:var(--cb-orange); }
.cb-search { display:inline-flex; align-items:center; justify-content:center; width:2.75rem; height:2.75rem; margin-right:.5rem; border-radius:50%; background:var(--cb-orange); color:#fff !important; }
.cb-search:hover { background:#cc4711; }
.cb-pill { display:inline-flex; align-items:center; gap:.5rem; padding:.5rem 1rem; border-radius:100vmax; font-weight:600; }
.cb-pill--peach { background:var(--cb-peach); }
.cb-pill--orange { background:var(--cb-orange); color:#fff !important; }
.cb-pill:hover span { text-decoration:underline; text-underline-offset:3px; }
.cb-join { padding:.875rem 1.5rem; }
.cb-toggle { display:none !important; }
.cb-mobile-extra { display:none; }
@media (max-width: 1260px) {
  .cb-header { position:sticky; top:0; padding:.5rem; background:#fff; box-shadow:0 0 .75rem rgba(0,0,0,.05); }
  .cb-wrapper { display:flex; gap:1.5rem; }
  .cb-wrapper::before { display:none; }
  .cb-logo { margin:0 auto 0 0; overflow:hidden; }
  .cb-toggle { display:flex !important; align-items:center; gap:.875rem; height:3rem; text-transform:uppercase; font-family:"Founders Grotesk Condensed","Arial Narrow",sans-serif !important; font-stretch:condensed; font-size:1.375rem !important; font-weight:700 !important; line-height:1; }
  .cb-toggle-icon, .cb-toggle-icon::before, .cb-toggle-icon::after { display:block; width:1.125rem; height:2px; border-radius:2px; background:currentColor; position:relative; }
  .cb-toggle-icon::before, .cb-toggle-icon::after { content:""; position:absolute; left:0; }
  .cb-toggle-icon::before { top:-6px; } .cb-toggle-icon::after { bottom:-6px; }
  .cb-open .cb-toggle-icon { background:transparent; }
  .cb-open .cb-toggle-icon::before { top:0; transform:rotate(-45deg); }
  .cb-open .cb-toggle-icon::after { bottom:0; transform:rotate(45deg); }
  .cb-search { order:3; margin:0; }
  .cb-join, .cb-toolbar, .cb-menu { display:none; }
  .cb-open .cb-menu { display:block; position:absolute; top:100%; left:0; right:0; max-height:calc(100dvh - 4rem); overflow:auto; background:#f9fafb; padding:2rem var(--cb-spc-x); text-align:center; }
  .cb-open .cb-list { flex-direction:column; gap:.75rem; }
  .cb-sub { position:static; transform:none; width:auto; box-shadow:none; margin-top:.75rem; text-align:left; }
  .cb-sub ul { columns:1; }
  .cb-sub-title { display:none; }
  .cb-open .cb-mobile-extra { display:flex; flex-wrap:wrap; justify-content:center; gap:.75rem; margin-top:1.75rem; padding-top:1.5rem; border-top:1px solid #ddd; }
  .cb-mobile-extra p { flex-basis:100%; margin:.5rem 0 0; font-size:.9375rem; font-weight:600; }
}
@media (max-width: 420px) { .cb-tagline { display:none; } }
.modal { z-index:2000 !important; }

/* Sub-nav : pages internes (Accueil / Tableau / Offres / Info / Résultats) */
.site-nav {
  background: #f8f8f8;
  display: flex; flex-wrap: wrap; gap: 2px; justify-content: center;
  padding: 0 24px;
  border-bottom: 1px solid #eee;
}
.site-nav a {
  color: #555; text-decoration: none;
  padding: 12px 16px; font-size: 13px; font-weight: 600;
  border-bottom: 3px solid transparent;
  transition: color .15s, border-color .15s, background .15s;
  white-space: nowrap;
}
.site-nav a:hover { color: #E7591C; background: #fff; }
.site-nav a.active { color: #E7591C; border-bottom-color: #E7591C; background: #fff; }
</style>
"""

def _nav(active: str, has_resultats: bool = False) -> str:
    pages = [
        ("index.html",    "🏠 Accueil"),
        ("tableau.html",  "📋 Tableau des postes"),
        ("offres.html",   "📄 Offres détaillées"),
        ("info.html",     "ℹ Informations pratiques"),
    ]
    if has_resultats:
        pages.insert(3, ("resultats.html", "✅ Résultats CDM"))

    links = ""
    for href, label in pages:
        cls = ' class="active"' if href == active else ""
        links += f'<a href="{href}"{cls}>{label}</a>'
    return f'<nav class="site-nav">{links}</nav>'


# ── Tableau filtrable ─────────────────────────────────────────────────────────

REQUIRED_COLS = [
    "Grand service", "Service", "Commune", "Libellé du poste",
    "Corps et restriction", "Agent remplacé", "N° AVE",
    "Première CDM d'ouverture du poste", "Statut",
]


def _render_tableau(df: pd.DataFrame, ave_to_url: dict, campaign: str, has_resultats: bool = False) -> str:
    # Corps badge colors (palette cyclique)
    CORPS_COLORS = [
        ("#1a6fb5","#dbeafe"), ("#b45309","#fef3c7"), ("#166534","#dcfce7"),
        ("#7c3aed","#ede9fe"), ("#be185d","#fce7f3"), ("#0e7490","#cffafe"),
        ("#92400e","#fef9c3"), ("#065f46","#d1fae5"), ("#4338ca","#e0e7ff"),
        ("#9d174d","#fdf2f8"),
    ]
    corps_color_map = {}
    color_idx = 0

    rows_data = []
    for _, row in df.iterrows():
        corps_raw = _e(str(row.get("Corps et restriction", "") or "").strip())
        commune   = _e(str(row.get("Commune", "") or "").strip())
        gs        = _e(str(row.get("Grand service", "") or "").strip())

        # Badges corps
        badges_html = ""
        for c in [x.strip() for x in corps_raw.split(";") if x.strip()]:  # déjà échappé
            if c not in corps_color_map:
                fg, bg = CORPS_COLORS[color_idx % len(CORPS_COLORS)]
                corps_color_map[c] = (fg, bg)
                color_idx += 1
            fg, bg = corps_color_map[c]
            badges_html += (
                f'<span style="display:inline-block;margin:1px 2px;padding:2px 8px;'
                f'border-radius:999px;font-size:11px;font-weight:700;'
                f'background:{bg};color:{fg};border:1px solid {fg}33">{c}</span>'
            )

        ferme = bool(row.get("_ferme", False))
        statut_val = str(row.get("Statut", "") or "")
        # Détecter fermeture même si _ferme absent (ex: après rechargement pickle)
        if "Ferm" in statut_val:
            ferme = True

        tds = []
        for col in REQUIRED_COLS:
            val = _e(str(row.get(col, "") or ""))
            # Remplacer O résiduel par Ouvert
            if col == "Statut" and val.strip().upper() == "O":
                val = "Ouvert"
            if col == "Corps et restriction":
                tds.append(f'<td data-val="{corps_raw}">{badges_html}</td>')
            elif col == "N° AVE":
                if val.strip():
                    anchor = re.sub(r'[^a-zA-Z0-9]', '-', val).strip('-')
                    display = f'<a href="offres.html#{anchor}" title="Voir la fiche détaillée">{val}</a>'
                else:
                    display = val
                tds.append(f'<td data-val="{val}">{display}</td>')
            else:
                tds.append(f'<td data-val="{val}">{val}</td>')

        row_cls = ' class="row-ferme"' if ferme else ""
        rows_data.append(
            f'<tr{row_cls} data-corps="{corps_raw}" data-commune="{commune}" data-gs="{gs}">'
            + "".join(tds) + "</tr>"
        )

    total = len(rows_data)
    body  = "\n".join(rows_data)

    return f"""<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CFDT — Postes ouverts {campaign}</title>
<link rel="stylesheet" href="assets/styles.css">
{_NAV_CSS}
<style>
/* ── Tableau amélioré ── */
.tbl-toolbar {{
  display:flex;flex-wrap:wrap;align-items:flex-end;gap:10px;
  margin:14px 0 10px;background:#fff8f5;border:1px solid rgba(231,89,28,.18);
  border-radius:14px;padding:14px 16px;
}}
.tbl-toolbar label {{display:flex;flex-direction:column;gap:3px;font-size:12px;font-weight:600;color:#666;}}
.tbl-toolbar select,.tbl-toolbar input[type=text] {{
  padding:8px 10px;border:1px solid #e0e0e0;border-radius:9px;font-size:13px;
  background:#fff;min-width:150px;
}}
.tbl-toolbar select:focus,.tbl-toolbar input:focus {{outline:none;border-color:#E7591C;}}
/* Multi-select dropdown (corps) */
.multi-select {{position:relative;display:inline-block;}}
.ms-trigger {{
  display:inline-flex;align-items:center;justify-content:space-between;gap:6px;
  padding:8px 12px;border:1px solid #e0e0e0;border-radius:9px;font-size:13px;
  background:#fff;min-width:200px;cursor:pointer;text-align:left;font-weight:500;color:#333;
}}
.ms-trigger:hover {{border-color:#E7591C;}}
.ms-trigger .ms-arrow {{font-size:10px;color:#999;}}
.ms-trigger .ms-count {{
  background:#E7591C;color:#fff;font-size:11px;font-weight:700;
  padding:1px 7px;border-radius:999px;margin-right:4px;
}}
.ms-panel {{
  position:absolute;top:calc(100% + 4px);left:0;z-index:50;
  background:#fff;border:1px solid #e0e0e0;border-radius:9px;
  box-shadow:0 4px 16px rgba(0,0,0,.1);
  min-width:280px;max-height:340px;overflow-y:auto;
  display:none;padding:6px 0;
}}
.multi-select.open .ms-panel {{display:block;}}
.ms-panel-actions {{
  display:flex;gap:6px;padding:6px 12px;border-bottom:1px solid #eee;
  font-size:12px;
}}
.ms-panel-actions button {{
  background:none;border:none;color:#E7591C;cursor:pointer;font-weight:600;padding:2px 4px;
}}
.ms-panel-actions button:hover {{text-decoration:underline;}}
.ms-panel label {{
  display:flex;align-items:center;gap:8px;padding:6px 12px;
  cursor:pointer;font-size:13px;
}}
.ms-panel label:hover {{background:#fff8f5;}}
.ms-panel label input[type=checkbox] {{accent-color:#E7591C;cursor:pointer;}}
.btn-reset {{
  background:#fff;color:#E7591C;border:1.5px solid #E7591C;
  padding:8px 16px;border-radius:999px;font-weight:700;cursor:pointer;font-size:13px;
  transition:background .15s;align-self:flex-end;
}}
.btn-reset:hover {{background:#fff3ee;}}
.tbl-info {{display:flex;align-items:center;justify-content:space-between;
  flex-wrap:wrap;gap:8px;margin:6px 0 8px;font-size:13px;color:#666;}}
.tbl-info strong {{color:#E7591C;}}
.per-page-sel {{padding:5px 8px;border:1px solid #e0e0e0;border-radius:8px;font-size:13px;}}
.tablewrap {{overflow-x:auto;border-radius:12px;border:1px solid #e8e8e8;}}
#tbl {{border-collapse:collapse;width:100%;table-layout:auto;}}
#tbl thead th {{
  position:sticky;top:0;z-index:10;
  background:#E7591C;color:#fff;
  padding:9px 8px;font-size:12px;font-weight:700;text-align:left;
  white-space:nowrap;user-select:none;
  border-right:1px solid rgba(255,255,255,.2);
  cursor:pointer;
  resize:horizontal;overflow:auto;min-width:60px;
}}
#tbl thead th:last-child {{border-right:none;}}
#tbl thead th .sort-icon {{margin-left:4px;opacity:.6;font-size:10px;}}
#tbl thead th.sort-asc .sort-icon::after {{content:'▲';}}
#tbl thead th.sort-desc .sort-icon::after {{content:'▼';}}
#tbl thead th:not(.sort-asc):not(.sort-desc) .sort-icon::after {{content:'⇅';}}
#tbl tbody tr {{border-bottom:2px solid #d0d0d0;transition:background .1s;}}
#tbl tbody tr:hover td {{background:#fff8f5;}}
#tbl tbody tr.row-ferme td {{
  text-decoration:line-through;color:#aaa;background:#fafafa;
}}
#tbl tbody tr.row-ferme:hover td {{background:#f5f5f5;}}
#tbl tbody td {{
  padding:7px 8px;font-size:13px;vertical-align:middle;
  border-right:1px solid #c8c8c8;
}}
#tbl tbody td:last-child {{border-right:none;}}
.pagination {{
  display:flex;align-items:center;justify-content:center;gap:6px;
  margin:14px 0 4px;flex-wrap:wrap;
}}
.page-btn {{
  min-width:34px;height:34px;border:1px solid #e0e0e0;background:#fff;
  border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;
  display:flex;align-items:center;justify-content:center;transition:all .15s;
}}
.page-btn:hover {{background:#fff3ee;border-color:#E7591C;color:#E7591C;}}
.page-btn.active {{background:#E7591C;color:#fff;border-color:#E7591C;}}
.page-btn:disabled {{opacity:.35;cursor:not-allowed;}}
.page-ellipsis {{padding:0 4px;color:#aaa;}}
</style>
</head><body>
{_CFDT_BANNER}
{_nav("tableau.html", has_resultats)}
<main class="container">
  <h1 style="margin:16px 0 4px;font-size:22px;">Postes ouverts — {campaign}</h1>

  <div class="tbl-toolbar">
    <label>Grand service
      <select id="f-gs"><option value="">Tous</option></select>
    </label>
    <label>Corps
      <div class="multi-select" id="ms-corps">
        <button type="button" class="ms-trigger" id="ms-corps-btn">
          <span id="ms-corps-label">Tous les corps</span>
          <span class="ms-arrow">▾</span>
        </button>
        <div class="ms-panel" id="ms-corps-panel">
          <div class="ms-panel-actions">
            <button type="button" id="ms-corps-all">Tout cocher</button>
            <button type="button" id="ms-corps-none">Tout décocher</button>
          </div>
          <div id="ms-corps-list"></div>
        </div>
      </div>
    </label>
    <label>Commune
      <select id="f-commune"><option value="">Toutes</option></select>
    </label>
    <label>Recherche libre
      <input id="f-q" type="text" placeholder="Libellé, N° AVE…">
    </label>
    <button id="reset" class="btn-reset">✕ Réinitialiser</button>
  </div>

  <div class="tbl-info">
    <span>Affichés&nbsp;<strong id="count">{total}</strong>&nbsp;/&nbsp;{total} postes</span>
    <span style="display:flex;align-items:center;gap:8px;">
      Lignes par page&nbsp;
      <select id="per-page" class="per-page-sel">
        <option value="50" selected>50</option>
        <option value="100">100</option>
        <option value="200">200</option>
        <option value="500">500</option>
        <option value="9999">Tout</option>
      </select>
    </span>
  </div>

  <div class="tablewrap">
  <table id="tbl">
    <thead><tr>
      <th data-col="0">Grand service<span class="sort-icon"></span></th>
      <th data-col="1">Service<span class="sort-icon"></span></th>
      <th data-col="2">Commune<span class="sort-icon"></span></th>
      <th data-col="3">Libellé du poste<span class="sort-icon"></span></th>
      <th data-col="4">Corps<span class="sort-icon"></span></th>
      <th data-col="5">Agent remplacé<span class="sort-icon"></span></th>
      <th data-col="6">N° AVE<span class="sort-icon"></span></th>
      <th data-col="7">CDM ouverture<span class="sort-icon"></span></th>
      <th data-col="8">Statut<span class="sort-icon"></span></th>
    </tr></thead>
    <tbody id="tbl-body">{body}</tbody>
  </table>
  </div>
  <div class="pagination" id="pagination"></div>
</main>
<footer>© CFDT Aviation Civile — <a href="index.html">Accueil</a></footer>
<script>
(function(){{
  const allRows = Array.from(document.querySelectorAll('#tbl-body tr'));
  const fgs  = document.getElementById('f-gs');
  const fm   = document.getElementById('f-commune');
  const fq   = document.getElementById('f-q');
  const cnt  = document.getElementById('count');
  const ppSel= document.getElementById('per-page');
  const pagEl= document.getElementById('pagination');

  // Populate simple filter dropdowns (Grand service, Commune)
  const sGs=new Set(), sC=new Set(), sM=new Set();
  allRows.forEach(r=>{{
    if(r.dataset.gs) sGs.add(r.dataset.gs);
    (r.dataset.corps||'').split(';').forEach(c=>{{if(c.trim())sC.add(c.trim())}});
    if(r.dataset.commune) sM.add(r.dataset.commune);
  }});
  function fill(sel,vals){{
    [...vals].sort((a,b)=>a.localeCompare(b,'fr')).forEach(v=>{{
      const o=document.createElement('option');o.value=v;o.textContent=v;sel.appendChild(o);
    }});
  }}
  fill(fgs,sGs);fill(fm,sM);

  // ── Multi-select corps (cases à cocher, OR logic) ───────────────────────
  const corpsSelected = new Set();
  const msCorps      = document.getElementById('ms-corps');
  const msCorpsBtn   = document.getElementById('ms-corps-btn');
  const msCorpsLabel = document.getElementById('ms-corps-label');
  const msCorpsList  = document.getElementById('ms-corps-list');

  function updateCorpsLabel(){{
    if(corpsSelected.size === 0){{
      msCorpsLabel.innerHTML = 'Tous les corps';
    }} else if(corpsSelected.size === 1){{
      msCorpsLabel.textContent = [...corpsSelected][0];
    }} else {{
      msCorpsLabel.innerHTML = '<span class="ms-count">'+corpsSelected.size+'</span>corps sélectionnés';
    }}
  }}

  [...sC].sort((a,b)=>a.localeCompare(b,'fr')).forEach(c=>{{
    const lbl = document.createElement('label');
    const cb  = document.createElement('input');
    cb.type='checkbox'; cb.value=c;
    cb.addEventListener('change', ()=>{{
      if(cb.checked) corpsSelected.add(c); else corpsSelected.delete(c);
      updateCorpsLabel();
      applyFilter();
    }});
    const sp = document.createElement('span');
    sp.textContent = c;
    lbl.appendChild(cb); lbl.appendChild(sp);
    msCorpsList.appendChild(lbl);
  }});

  msCorpsBtn.addEventListener('click', e=>{{
    e.stopPropagation();
    msCorps.classList.toggle('open');
  }});
  msCorps.addEventListener('click', e=>e.stopPropagation());
  document.addEventListener('click', ()=>msCorps.classList.remove('open'));

  document.getElementById('ms-corps-all').addEventListener('click', ()=>{{
    msCorpsList.querySelectorAll('input').forEach(i=>{{ i.checked=true; corpsSelected.add(i.value); }});
    updateCorpsLabel(); applyFilter();
  }});
  document.getElementById('ms-corps-none').addEventListener('click', ()=>{{
    msCorpsList.querySelectorAll('input').forEach(i=>{{ i.checked=false; }});
    corpsSelected.clear();
    updateCorpsLabel(); applyFilter();
  }});

  function corpsRowMatches(rowCorps){{
    if(corpsSelected.size === 0) return true;
    const rowSet = (rowCorps||'').split(';').map(s=>s.trim()).filter(Boolean);
    for(const sel of corpsSelected) if(rowSet.includes(sel)) return true;
    return false;
  }}

  function norm(s){{return(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();}}

  // State
  let filtered = allRows.slice();
  let sortCol = -1, sortAsc = true;
  let page = 1;

  function getPerPage(){{ return parseInt(ppSel.value)||50; }}

  // Filter
  function applyFilter(){{
    filtered = allRows.filter(r=>{{
      return(
        (!fgs.value || r.dataset.gs===fgs.value) &&
        corpsRowMatches(r.dataset.corps) &&
        (!fm.value  || r.dataset.commune===fm.value) &&
        (!fq.value  || norm(r.innerText).includes(norm(fq.value)))
      );
    }});
    page = 1;
    renderTable();
  }}

  // Sort
  document.querySelectorAll('#tbl thead th').forEach(th=>{{
    th.addEventListener('click', ()=>{{
      const col = parseInt(th.dataset.col);
      if(sortCol===col) sortAsc=!sortAsc; else{{sortCol=col;sortAsc=true;}}
      document.querySelectorAll('#tbl thead th').forEach(t=>t.classList.remove('sort-asc','sort-desc'));
      th.classList.add(sortAsc?'sort-asc':'sort-desc');
      filtered.sort((a,b)=>{{
        const va=(a.cells[col]?.dataset.val||a.cells[col]?.textContent||'').trim();
        const vb=(b.cells[col]?.dataset.val||b.cells[col]?.textContent||'').trim();
        const n = va.localeCompare(vb,'fr',{{numeric:true}});
        return sortAsc?n:-n;
      }});
      renderTable();
    }});
  }});

  // Render table + pagination
  function renderTable(){{
    const pp = getPerPage();
    const total = filtered.length;
    const pages = Math.max(1, Math.ceil(total/pp));
    if(page>pages) page=pages;
    cnt.textContent = total;

    const tbody = document.getElementById('tbl-body');
    // Hide all
    allRows.forEach(r=>{{ r.style.display='none'; }});
    // Show current page
    const start=(page-1)*pp, end=Math.min(start+pp,total);
    for(let i=start;i<end;i++){{ filtered[i].style.display=''; }}

    renderPagination(pages);
  }}

  function renderPagination(pages){{
    pagEl.innerHTML='';
    if(pages<=1)return;

    function btn(label,pg,disabled,active){{
      const b=document.createElement('button');
      b.className='page-btn'+(active?' active':'');
      b.textContent=label;
      b.disabled=disabled;
      if(!disabled)b.addEventListener('click',()=>{{page=pg;renderTable();}});
      return b;
    }}

    pagEl.appendChild(btn('‹',page-1,page===1,false));

    // Page numbers with ellipsis
    const range=[];
    for(let i=1;i<=pages;i++){{
      if(i===1||i===pages||Math.abs(i-page)<=2) range.push(i);
      else if(range[range.length-1]!=='…') range.push('…');
    }}
    range.forEach(p=>{{
      if(p==='…'){{
        const s=document.createElement('span');s.className='page-ellipsis';s.textContent='…';
        pagEl.appendChild(s);
      }} else {{
        pagEl.appendChild(btn(p,p,false,p===page));
      }}
    }});

    pagEl.appendChild(btn('›',page+1,page===pages,false));
  }}

  // Events
  [fgs,fm,fq].forEach(el=>el.addEventListener('input',applyFilter));
  ppSel.addEventListener('change',()=>{{page=1;renderTable();}});
  document.getElementById('reset').addEventListener('click',()=>{{
    fgs.value='';fm.value='';fq.value='';
    msCorpsList.querySelectorAll('input').forEach(i=>{{ i.checked=false; }});
    corpsSelected.clear();
    updateCorpsLabel();
    applyFilter();
  }});

  applyFilter();
}})();
</script>
</body></html>"""


# ── Construction des offres combinées CSP + SIRH ─────────────────────────────

def _build_combined_offers(df_csp, df_sirh) -> list[dict]:
    """
    Fusionne CSP et SIRH par N° AVE avec SIRH prioritaire.
    - Quand les deux sources ont la même AVE : les champs descriptifs SIRH
      (titre, employeur, description, missions, profil, contacts, etc.)
      écrasent ceux du CSP. CSP sert de fallback si SIRH est vide.
    - Les champs CSP-only (url, télétravail, type contrat, expérience,
      rémunération) sont toujours conservés.
    - Le champ `source` vaut 'SIRH+CSP', 'SIRH' ou 'CSP' selon les présences.
    """
    def _ave_key(v) -> str:
        return re.sub(r'[^\d]', '', str(v or '')).lstrip('0')

    def _clean(v) -> str:
        if v is None or pd.isna(v):
            return ''
        s = str(v).strip()
        return '' if s.lower() == 'nan' else s

    # Index CSP par AVE normalisé
    csp_by_ave: dict[str, dict] = {}
    if df_csp is not None and not df_csp.empty:
        for _, row in df_csp.iterrows():
            k = _ave_key(row.get('numero_ave', ''))
            if k:
                csp_by_ave[k] = row

    # Index SIRH par AVE normalisé
    sirh_by_ave: dict[str, dict] = {}
    if df_sirh is not None and not df_sirh.empty:
        for _, row in df_sirh.iterrows():
            k = _ave_key(row.get('N° AVE SIRH', ''))
            if k:
                sirh_by_ave[k] = row

    combined: list[dict] = []
    all_aves = set(csp_by_ave) | set(sirh_by_ave)

    for k in sorted(all_aves):
        csp_row  = csp_by_ave.get(k)
        sirh_row = sirh_by_ave.get(k)

        # Helpers
        def csp(f: str) -> str:
            return _clean(csp_row.get(f, '')) if csp_row is not None else ''

        def sirh(f: str) -> str:
            return _clean(sirh_row.get(f, '')) if sirh_row is not None else ''

        # Localisation SIRH : extraite depuis Définition, sinon Unité SIRH
        localisation_sirh = ''
        if sirh_row is not None:
            defin = sirh('Définition')
            m = re.search(r'[Ll]ocalisation\s+du\s+poste\s*:\s*([^.]+)', defin)
            localisation_sirh = m.group(1).strip() if m else sirh('Unité SIRH')

        # Contacts SIRH formatés (nom / tél / email + commentaires éventuels)
        contacts_sirh = ''
        if sirh_row is not None:
            contacts_sirh = '\n'.join(filter(None, [
                sirh('Responsable nom'),
                sirh('Responsable tél'),
                sirh('Responsable email'),
                sirh('Commentaires'),
            ]))

        # Source
        if sirh_row is not None and csp_row is not None:
            source = 'SIRH+CSP'
        elif sirh_row is not None:
            source = 'SIRH'
        else:
            source = 'CSP'

        # AVE original (préférer la forme SIRH si dispo)
        ave_raw = sirh('N° AVE SIRH') or csp('numero_ave')

        # Fusion champ par champ : SIRH prioritaire, CSP en fallback
        entry = {
            'numero_ave':       ave_raw,
            'titre':            sirh('Poste SIRH')         or csp('titre'),
            'employeur':        sirh('Grand service SIRH') or csp('employeur'),
            'localisation':     localisation_sirh          or csp('localisation'),
            'domaine':          sirh('Filière SIRH') or sirh('Métier SIRH') or csp('domaine'),
            'description':      sirh('Définition')         or csp('description'),
            'missions':         sirh('Tâches')             or csp('missions'),
            'profil_recherche': sirh('Profil')             or csp('profil_recherche'),
            'contacts':         contacts_sirh              or csp('contacts'),
            'restrictions':     sirh('Restrictions grades'),
            'additif':          sirh('Additif/Modificatif'),
            # Champs CSP-only : toujours pris du CSP si présent
            'url':              csp('url'),
            'teletravail':      csp('teletravail'),
            'type_contrat':     csp('type_contrat'),
            'experience':       csp('experience'),
            'remuneration':     csp('remuneration'),
            'source':           source,
        }
        combined.append(entry)

    return combined


# ── Page offres détaillées ────────────────────────────────────────────────────

def _render_offres(has_sirh: bool = False, has_resultats: bool = False) -> str:
    banner = "" if has_sirh else """
  <div style="background:#fff8e1;border-left:4px solid #E7591C;border-radius:6px;padding:12px 16px;margin-bottom:18px;font-size:14px;color:#444;">
    ⏳ <strong>Mise à jour en cours</strong> — Les fiches détaillées des offres de mobilité seront disponibles au plus tard en début de semaine prochaine. Le tableau des postes ouverts est déjà accessible et sera enrichi des descriptions complètes dès que possible.
  </div>"""
    source_filter = """
    <select id="sel-source"><option value="">Toutes sources</option>
      <option value="SIRH+CSP">SIRH + CSP (les deux)</option>
      <option value="SIRH">SIRH uniquement</option>
      <option value="CSP">CSP uniquement</option>
    </select>""" if has_sirh else ""
    data_file = "data/offres.json" if has_sirh else "data/offres_csp.json"
    source_filter_js = "&&(!selSource.value||x.source===selSource.value)" if has_sirh else ""
    source_sel_init  = "const selSource=document.getElementById('sel-source');" if has_sirh else "const selSource={value:'',addEventListener:()=>{}};"
    source_listener  = "selSource," if has_sirh else ""
    titre = "Offres DGAC et Météo-France"

    return f"""<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CFDT — Offres détaillées</title>
<link rel="stylesheet" href="assets/styles.css">
<style>
.badge-source{{display:inline-flex;padding:2px 7px;border-radius:999px;font-size:10px;font-weight:700;margin-left:4px;}}
.badge-csp{{background:#dbeafe;color:#1a6fb5;border:1px solid #1a6fb533;}}
.badge-sirh{{background:#dcfce7;color:#166534;border:1px solid #16653433;}}
.badge-sirh-csp{{background:#ede9fe;color:#7c3aed;border:1px solid #7c3aed33;}}
@keyframes card-flash{{0%{{box-shadow:0 0 0 4px #E7591C88;}}100%{{box-shadow:none;}}}}
.card-highlight{{animation:card-flash 1.8s ease-out 2;outline:2px solid #E7591C;}}
</style>
{_NAV_CSS}
</head><body>
{_CFDT_BANNER}
{_nav("offres.html", has_resultats)}
<main class="container">
  <h2>{titre}</h2>{banner}
  <div class="controls">
    <input id="q" type="text" placeholder="Titre, domaine, commune, N° AVE…">
    <select id="sel-emp"><option value="">Tous employeurs</option></select>
    <select id="sel-dom"><option value="">Tous domaines</option></select>{source_filter}
  </div>
  <p id="count" class="small">—</p>
  <div id="grid" class="grid"></div>
</main>
<div id="modal" class="modal">
  <div class="panel">
    <span class="close" id="close-btn">✕</span>
    <h3 id="m-title"></h3>
    <div class="small" id="m-meta"></div><hr>
    <h4>Description</h4><div id="m-desc"></div>
    <h4>Missions</h4><div id="m-mis"></div>
    <h4>Profil recherché</h4><div id="m-pro"></div>
    <h4>Contacts</h4><div id="m-con"></div>
    <p><a id="m-link" class="btn" target="_blank" rel="noopener">Fiche officielle CSP ↗</a></p>
  </div>
</div>
<footer>© CFDT Aviation Civile</footer>
<script>
let DATA=[];
function norm(s){{return(s||'').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().trim();}}
function normId(s){{return(s||'').replace(/[^a-zA-Z0-9]/g,'-').replace(/-+/g,'-').replace(/^-|-$/g,'');}}
const q=document.getElementById('q');
const selEmp=document.getElementById('sel-emp');
const selDom=document.getElementById('sel-dom');
{source_sel_init}
const cnt=document.getElementById('count');
const grid=document.getElementById('grid');
function fillFilters(){{
  const emp=new Set(),dom=new Set();
  DATA.forEach(x=>{{if(x.employeur)emp.add(x.employeur);if(x.domaine)dom.add(x.domaine);}});
  [...emp].sort((a,b)=>a.localeCompare(b,'fr')).forEach(v=>{{
    const o=document.createElement('option');o.value=v;o.textContent=v;selEmp.appendChild(o);}});
  [...dom].sort((a,b)=>a.localeCompare(b,'fr')).forEach(v=>{{
    const o=document.createElement('option');o.value=v;o.textContent=v;selDom.appendChild(o);}});
}}
function matches(x){{
  const qq=norm(q.value);
  return(!qq||[x.titre,x.domaine,x.localisation,x.numero_ave].some(v=>norm(v).includes(qq)))
    &&(!selEmp.value||x.employeur===selEmp.value)
    &&(!selDom.value||x.domaine===selDom.value)
    {source_filter_js};
}}
function render(){{
  grid.innerHTML='';
  const r=DATA.filter(matches);
  cnt.textContent=r.length+' offre(s)';
  r.forEach(x=>{{
    const srcBadge=x.source?`<span class="badge-source badge-${{x.source.toLowerCase().replace(/[^a-z]+/g,'-')}}">${{_esc(x.source)}}</span>`:'';
    const additifBadge=x.additif?`<span class="badge-source" style="background:#fef3c7;color:#b45309;border:1px solid #b4530933;">${{_esc(x.additif)}}</span>`:'';
    const d=document.createElement('div');d.className='card';
    d.id='offer-'+normId(x.numero_ave);
    const url=_safeUrl(x.url);
    d.innerHTML=`<div class="small"><span class="badge">${{_esc(x.numero_ave||'N/A')}}</span> ${{_esc(x.employeur)}}${{srcBadge}}${{additifBadge}}</div>
      <h3 style="margin:.4rem 0 .6rem">${{_esc(x.titre)}}</h3>
      <div class="small">${{_esc(x.localisation)}} · ${{_esc(x.domaine)}}</div>
      <a class="btn" href="#" data-id="${{_esc(x.numero_ave)}}">Détails…</a>
      ${{url?`<a class="btn" href="${{_esc(url)}}" target="_blank" rel="noopener">CSP ↗</a>`:''}}`;
    d.querySelector('a[data-id]').addEventListener('click',e=>{{e.preventDefault();openModal(x);}});
    grid.appendChild(d);
  }});
}}
function checkHash(){{
  const hash=location.hash.slice(1);
  if(!hash)return;
  const target=DATA.find(x=>normId(x.numero_ave)===hash);
  if(target){{
    openModal(target);
    const card=document.getElementById('offer-'+hash);
    if(card){{card.scrollIntoView({{behavior:'smooth',block:'center'}});card.classList.add('card-highlight');}}
  }}
}}
fetch('{data_file}').then(r=>r.json()).then(d=>{{DATA=d;fillFilters();render();checkHash();}});
[q,selEmp,selDom,{source_listener}].forEach(el=>el&&el.addEventListener('input',render));
/* ── Formateurs Option C ─────────────────────────────────────────── */
function _esc(s){{return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}}
function _safeUrl(u){{u=String(u||'').trim();return /^https?:\/\//i.test(u)?u:'';}}
const _SF=['Savoir-faire','Savoir faire'],_SE=['Savoir-être','Savoir être'],_OT=['Connaissances','Techniques de base'];
function _kwT(kw){{return _SF.some(k=>kw.startsWith(k))?'sf':_SE.some(k=>kw.startsWith(k))?'se':'ot';}}
function _splitSecs(s){{
  s=(s||'').replace(/\s+/g,' ').trim();
  const hits=[];
  for(const kw of[..._SF,..._SE,..._OT]){{
    let i=s.indexOf(kw);
    while(i!==-1){{if(i===0||s[i-1]===' ')hits.push({{i,kw,end:i+kw.length}});i=s.indexOf(kw,i+1);}}
  }}
  const dr=/(^| )Domaine\s+[A-ZÀ-Ü][A-Za-zÀ-ÿ\s]+(?=\s*:)/g;
  let dm;while((dm=dr.exec(s))!==null)hits.push({{i:dm.index,kw:dm[0].trim(),end:dm.index+dm[0].length}});
  hits.sort((a,b)=>a.i-b.i||(b.kw.length-a.kw.length));
  const u=[];for(const h of hits){{const p=u[u.length-1];if(p&&h.i===p.i)continue;u.push(h);}}
  if(!u.length)return[{{kw:null,content:s,type:'ot'}}];
  const secs=[];
  for(let j=0;j<u.length;j++){{
    const h=u[j],cEnd=u[j+1]?u[j+1].i:s.length;
    secs.push({{kw:h.kw,content:s.slice(h.end,cEnd).replace(/^\s*:?\s*/,'').trim(),type:_kwT(h.kw)}});
  }}
  if(u[0].i>0)secs.unshift({{kw:null,content:s.slice(0,u[0].i).trim(),type:'ot'}});
  return secs;
}}
function _parseItems(c){{
  c=(c||'').replace(/\s+/g,' ').trim().replace(/^:?\s*-\s+/,'');
  if(!c)return{{type:'empty',items:[]}};
  if(/\s*;\s*-\s+/.test(c)||/[\s,]-\s+[A-ZÁÀÉÈÙÎÏÔÇ]/.test(c)){{
    const it=c.split(/\s*(?:;|,)?\s*-\s+/).map(x=>x.trim().replace(/,$/,'')).filter(Boolean);
    if(it.length>1)return{{type:'bullets',items:it}};
  }}
  try{{const sp=c.split(/(?<=[a-záàéèùîïôç'\\/])\s+(?=[A-ZÁÀÉÈÙÎÏÔÇ][a-záàéèùîïôç\s]+:)/g);
    if(sp.length>1)return{{type:'subcats',items:sp.map(x=>x.trim()).filter(Boolean)}};}}catch(_){{}}
  try{{const pp=c.split(/(?<=[a-záàéèùîïôç'])\s+(?=[A-ZÁÀÉÈÙÎÏÔÇ][a-záàéèùîïôç])/g);
    if(pp.length>1)return{{type:'plain-items',items:pp.map(x=>x.trim()).filter(Boolean)}};}}catch(_){{}}
  return{{type:'plain',items:[c]}};
}}
const _COL={{sf:'#D85A30',se:'#185FA5',ot:'#3B6D11'}};
function _rItems(p,col){{
  if(!p||p.type==='empty')return'';
  const c=col||'#E7591C';
  const row=i=>`<div style="display:flex;gap:7px;font-size:14px;line-height:1.55;margin-bottom:5px"><span style="color:${{c}};flex-shrink:0">▸</span><span>${{_esc(i)}}</span></div>`;
  if(p.type==='bullets'||p.type==='plain-items')return p.items.map(row).join('');
  if(p.type==='subcats')return p.items.map(i=>{{
    const m=i.match(/^([^:]+:)\s*(.*)$/s);
    return m?`<div style="display:flex;gap:7px;font-size:14px;line-height:1.55;margin-bottom:5px"><span style="color:${{c}};flex-shrink:0">▸</span><span><strong>${{_esc(m[1])}}</strong> ${{_esc(m[2])}}</span></div>`:row(i);
  }}).join('');
  return`<p style="font-size:14px;line-height:1.6;margin:0 0 4px">${{_esc(p.items[0])}}</p>`;
}}
function _rSec(sec,first){{
  const col=_COL[sec.type]||_COL.ot,p=_parseItems(sec.content);
  let h='';
  if(sec.kw)h=`<div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:${{col}};border-bottom:1.5px solid ${{col}}44;padding-bottom:3px;margin:${{first?0:14}}px 0 7px">${{_esc(sec.kw)}}</div>`;
  return h+_rItems(p,col);
}}
function _fmtProfil(s){{
  if(!s)return'<p style="color:#aaa;font-size:14px">—</p>';
  const secs=_splitSecs(s);
  if(secs.length<=1)return secs.map((x,i)=>_rSec(x,i===0)).join('');
  const mid=Math.ceil(secs.length/2),cs='border:0.5px solid #e8e8e8;border-radius:8px;padding:11px 12px;background:#fafafa;min-width:0';
  return`<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px"><div style="${{cs}}">${{secs.slice(0,mid).map((x,i)=>_rSec(x,i===0)).join('')}}</div><div style="${{cs}}">${{secs.slice(mid).map((x,i)=>_rSec(x,i===0)).join('')}}</div></div>`;
}}
function _fmtTaches(s){{
  if(!s)return'<p style="color:#aaa;font-size:14px">—</p>';
  const e=(s||'').replace(/\s+/g,' ').trim();
  const m=e.match(/^(.+?)\s*:\s*-\s+(.+)$/s);
  if(!m)return`<p style="font-size:14px;line-height:1.6;margin:0">${{_esc(e)}}</p>`;
  const items=m[2].split(/\s*;\s*-\s+/).map(x=>x.trim()).filter(Boolean);
  if(!items.length)return`<p style="font-size:14px;line-height:1.6;margin:0">${{_esc(e)}}</p>`;
  return`<div style="border-left:3px solid #E7591C;background:#fff5f1;padding:5px 10px;border-radius:0 5px 5px 0;font-size:13px;font-weight:600;color:#E7591C;margin-bottom:9px">${{_esc(m[1].trim())}} :</div>${{items.map(i=>`<div style="display:flex;gap:7px;font-size:14px;line-height:1.55;margin-bottom:5px"><span style="color:#E7591C;flex-shrink:0">▸</span><span>${{_esc(i)}}</span></div>`).join('')}}`;
}}
function _fmtDef(s){{
  if(!s)return'<p style="color:#aaa;font-size:14px">—</p>';
  const e=(s||'').replace(/\s+/g,' ').trim(),ws=e.split(' ');
  let ti=0;while(ti<ws.length&&(/^[A-ZÁÀÉÈÙÎÏÔÇ:0-9-]{{2,}}$/.test(ws[ti])||ws[ti]===':'))ti++;
  if(ti>=2){{const t=ws.slice(0,ti).join(' ').replace(/\s*:$/,'').trim(),r=ws.slice(ti).join(' ').trim();
    return`<div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:#E7591C;margin-bottom:6px">${{_esc(t)}}</div><p style="font-size:14px;line-height:1.6;margin:0">${{_esc(r)}}</p>`;}}
  return`<p style="font-size:14px;line-height:1.6;margin:0">${{_esc(e)}}</p>`;
}}
function _fmtContacts(s){{
  if(!s)return'<p style="color:#aaa;font-size:14px">—</p>';
  return(s||'').split(/\\r?\\n/).map(l=>l.trim()).filter(Boolean).map(l=>{{
    if(/^[\w.+\-]+@[\w\-]+\.\w+$/.test(l))return`<div style="font-size:14px;line-height:1.9"><a href="mailto:${{_esc(l)}}">${{_esc(l)}}</a></div>`;
    if(/^[+\d\s.()\-]{{8,}}$/.test(l))return`<div style="font-size:14px;line-height:1.9">☎ ${{_esc(l)}}</div>`;
    return`<div style="font-size:14px;line-height:1.9">${{_esc(l)}}</div>`;
  }}).join('');
}}
/* ─────────────────────────────────────────────────────────────────── */
const modal=document.getElementById('modal');
function openModal(x){{
  document.getElementById('m-title').textContent=x.titre||'';
  const restrLine=x.restrictions?`\n⚠ Restrictions : ${{x.restrictions}}`:'';
  const additifLine=x.additif?` · ${{x.additif}}`:'';
  document.getElementById('m-meta').textContent=`${{x.numero_ave||''}} — ${{x.employeur||''}} — ${{x.localisation||''}}${{additifLine}}${{restrLine}}`;
  document.getElementById('m-desc').innerHTML=_fmtDef(x.description||'');
  document.getElementById('m-mis').innerHTML=_fmtTaches(x.missions||'');
  document.getElementById('m-pro').innerHTML=_fmtProfil(x.profil_recherche||'');
  document.getElementById('m-con').innerHTML=_fmtContacts(x.contacts||'');
  const l=document.getElementById('m-link');
  const su=_safeUrl(x.url);
  if(su){{l.href=su;l.style.display='inline-flex';}}else{{l.style.display='none';}}
  modal.classList.add('open');
}}
document.getElementById('close-btn').addEventListener('click',()=>modal.classList.remove('open'));
modal.addEventListener('click',e=>{{if(e.target===modal)modal.classList.remove('open');}});
</script>
</body></html>"""




# ── Page résultats CDM ────────────────────────────────────────────────────────

def _render_resultats(df_complet: pd.DataFrame, campaign: str) -> str:
    """Page publique des résultats CDM : chiffres clés + tableau groupé par grand service."""
    df = df_complet.copy()
    df["_ave_sort"] = pd.to_numeric(
        df["N° AVE"].astype(str).str.extract(r"(\d+)", expand=False), errors="coerce")
    df = df.sort_values(["Grand service", "_ave_sort"]).drop(columns=["_ave_sort"])

    def s_(v):
        return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()

    def poste_parts(lib):
        lib = s_(lib)
        m = re.match(r"^\s*(\d+)\s+postes?\s*[—–-]\s*(.*)$", lib)
        n, rest = (int(m.group(1)), m.group(2)) if m else (1, lib)
        title, _, uo = rest.partition("*")
        return n, title.strip() or rest.strip(), uo.strip()

    def chips(corps):
        return "".join(f'<span class="r-chip">{_e(c.strip())}</span>'
                       for c in s_(corps).split(";") if c.strip())

    ferme_mask = df["Statut"].astype(str).str.contains("Ferm", na=False) if "Statut" in df.columns else pd.Series(False, index=df.index)
    if "_ferme" in df.columns:
        ferme_mask |= df["_ferme"].fillna(False).astype(bool)
    retenu_mask = df["Agent retenu"].fillna("").astype(str).str.strip() != ""
    ferme_mask &= ~retenu_mask
    total = int((~ferme_mask).sum())
    n_ret = int(retenu_mask.sum())
    n_vac = total - n_ret
    n_fer = int(ferme_mask.sum())
    pct = round(100 * n_ret / total) if total else 0

    rows, current_gs = [], None
    gs_stats = df[~ferme_mask].assign(_r=retenu_mask[~ferme_mask]) \
                 .groupby("Grand service")["_r"].agg(["size", "sum"])
    for _, row in df.iterrows():
        gs = s_(row.get("Grand service"))
        if gs != current_gs:
            current_gs = gs
            st = gs_stats.loc[gs] if gs in gs_stats.index else None
            info = f'{int(st["size"])} poste(s) · {int(st["sum"])} pourvu(s)' if st is not None else ""
            rows.append(f'<tr class="gs-head" data-gs="{_e(gs)}"><td colspan="5">'
                        f'<span class="gs-name">{_e(gs) or "—"}</span><span class="gs-info">{info}</span></td></tr>')
        agent = s_(row.get("Agent retenu"))
        n, title, uo = poste_parts(row.get("Libellé du poste"))
        service, commune = s_(row.get("Service")), re.sub(r"\s+CEDEX.*$", "", s_(row.get("Commune")), flags=re.I)
        ave = s_(row.get("N° AVE"))
        anchor = re.sub(r"[^a-zA-Z0-9]", "-", ave).strip("-")
        nb = f'<span class="r-nb">{n} postes</span>' if n > 1 else ""
        ferme = bool(ferme_mask.loc[_])
        if agent:
            corps_r = s_(row.get("Corps retenu"))
            result = (f'<span class="r-agent">{_e(agent)}</span>'
                      + (f'<span class="r-chip r-chip--ok">{_e(corps_r)}</span>' if corps_r else ""))
        elif ferme:
            result = '<span class="r-vac r-vac--closed">Poste fermé</span>'
        else:
            result = '<span class="r-vac">Non pourvu</span>'
        status = "retenu" if agent else ("ferme" if ferme else "vacant")
        rows.append(
            f'<tr class="row-{status}" data-gs="{_e(gs)}" data-corps="{_e(row.get("Corps et restriction",""))}">'
            f'<td data-label="Poste"><div class="r-title">{_e(title)} {nb}</div>'
            f'<div class="r-sub">{_e(service)}{(" · <span class=r-uo>" + _e(uo) + "</span>") if uo else ""}</div></td>'
            f'<td data-label="Lieu">{_e(commune)}</td>'
            f'<td data-label="Corps ouverts">{chips(row.get("Corps et restriction"))}</td>'
            f'<td data-label="Résultat">{result}</td>'
            f'<td data-label="N° AVE"><a class="r-ave" href="offres.html#{_e(anchor)}" title="Voir la fiche du poste">{_e(ave)}</a></td>'
            f'</tr>')

    html = r"""<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CFDT — Résultats CDM %%CAMPAIGN%%</title>
<link rel="stylesheet" href="assets/styles.css">
%%NAVCSS%%
<style>
.r-wrap { max-width:1180px; margin:0 auto; padding:24px 22px 40px; }
.r-head h1 { margin:0 0 4px; font-size:28px; }
.r-head p { margin:0 0 20px; color:#666; }
.r-kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px; margin-bottom:22px; }
.r-kpi { background:#fff; border:1px solid #ececec; border-radius:16px; padding:16px 20px; box-shadow:0 2px 10px rgba(0,0,0,.04); }
.r-kpi b { display:block; font-size:30px; line-height:1.1; }
.r-kpi span { font-size:13px; color:#666; }
.r-kpi--ok b { color:#1f7a3f; } .r-kpi--vac b { color:#E7591C; }
.r-bar { height:8px; border-radius:99px; background:#fde3d6; overflow:hidden; margin-top:10px; }
.r-bar i { display:block; height:100%; background:#1f7a3f; }
.r-tools { display:flex; flex-wrap:wrap; gap:10px; align-items:center; background:#fff8f5; border:1px solid rgba(231,89,28,.18); border-radius:14px; padding:12px 14px; margin-bottom:14px; }
.r-tools select, .r-tools input { padding:9px 12px; border:1px solid #e2e2e2; border-radius:10px; font-size:14px; background:#fff; }
.r-tools input { flex:1; min-width:200px; }
.r-seg { display:inline-flex; border:1px solid #e2e2e2; border-radius:10px; overflow:hidden; background:#fff; }
.r-seg button { border:0; background:none; padding:9px 14px; font-size:13px; font-weight:600; color:#555; cursor:pointer; }
.r-seg button.on { background:#E7591C; color:#fff; }
.r-count { font-size:13px; color:#666; margin:0 0 8px; }
.r-table { width:100%; border-collapse:separate; border-spacing:0; background:#fff; border:1px solid #ececec; border-radius:14px; overflow:hidden; font-size:14px; }
.r-table th { position:sticky; top:0; z-index:1; background:#fafafa; text-align:left; font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:#777; padding:10px 14px; border-bottom:1px solid #ececec; }
.r-table td { padding:11px 14px; border-bottom:1px solid #f1f1f1; vertical-align:top; }
.r-table tr.row-retenu:hover td, .r-table tr.row-vacant:hover td { background:#fffaf7; }
.gs-head td { background:#f6f6f7; border-bottom:1px solid #ececec; padding:9px 14px; }
.gs-name { font-weight:700; color:#222; margin-right:10px; }
.gs-info { font-size:12px; color:#777; }
.r-title { font-weight:600; color:#222; }
.r-sub { font-size:12.5px; color:#777; margin-top:2px; }
.r-uo { color:#aaa; }
.r-nb { display:inline-block; font-size:11px; font-weight:700; color:#E7591C; background:rgba(231,89,28,.08); border-radius:99px; padding:1px 8px; margin-left:4px; vertical-align:1px; }
.r-chip { display:inline-block; font-size:11px; font-weight:600; color:#555; background:#f1f1f3; border-radius:99px; padding:2px 8px; margin:1px 3px 1px 0; white-space:nowrap; }
.r-chip--ok { color:#1f7a3f; background:#e6f4ea; margin-left:6px; }
.r-agent { font-weight:700; color:#1f7a3f; }
.r-vac { display:inline-block; font-size:12px; font-weight:600; color:#999; border:1px dashed #ccc; border-radius:99px; padding:2px 10px; }
.r-vac--closed { border-style:solid; color:#bbb; text-decoration:line-through; }
tr.row-ferme td { opacity:.6; }
.r-ave { font-variant-numeric:tabular-nums; color:#888; font-size:13px; }
.r-ave:hover { color:#E7591C; }
@media (max-width: 760px) {
  .r-table, .r-table tbody, .r-table tr, .r-table td { display:block; width:100%; }
  .r-table thead { display:none; }
  .r-table tr.row-retenu, .r-table tr.row-vacant { padding:10px 4px; border-bottom:1px solid #eee; }
  .r-table td { border:0; padding:3px 12px; }
  .r-table td[data-label="Corps ouverts"]::before, .r-table td[data-label="N° AVE"]::before { content:attr(data-label) " : "; font-size:12px; color:#999; }
}
@media print { .cb-header, .site-nav, .r-tools { display:none !important; } .r-table th { position:static; } }
</style>
</head><body>
%%BANNER%%
%%NAV%%
<main class="r-wrap">
  <div class="r-head">
    <h1>Résultats de la CDM</h1>
    <p>%%CAMPAIGN%%</p>
  </div>
  <div class="r-kpis">
    <div class="r-kpi"><b>%%TOTAL%%</b><span>postes ouverts</span></div>
    <div class="r-kpi r-kpi--ok"><b>%%RET%%</b><span>postes pourvus (%%PCT%% %)</span><div class="r-bar"><i style="width:%%PCT%%%"></i></div></div>
    <div class="r-kpi r-kpi--vac"><b>%%VAC%%</b><span>postes non pourvus%%FER%%</span></div>
  </div>
  <div class="r-tools">
    <div class="r-seg" id="f-status">
      <button type="button" data-v="" class="on">Tous</button>
      <button type="button" data-v="retenu">Pourvus</button>
      <button type="button" data-v="vacant">Non pourvus</button>
    </div>
    <select id="f-gs"><option value="">Tous les grands services</option></select>
    <select id="f-corps"><option value="">Tous les corps</option></select>
    <input id="f-q" type="search" placeholder="Rechercher un nom, un poste, une ville…">
  </div>
  <p class="r-count"><strong id="count"></strong> poste(s) affiché(s)</p>
  <table id="tbl" class="r-table">
    <thead><tr><th>Poste</th><th>Lieu</th><th>Corps ouverts</th><th>Résultat</th><th>N° AVE</th></tr></thead>
    <tbody>%%BODY%%</tbody>
  </table>
</main>
<footer>© CFDT Aviation Civile</footer>
<script>
(function(){
const rows=[...document.querySelectorAll('#tbl tbody tr:not(.gs-head)')];
const heads=[...document.querySelectorAll('#tbl tbody tr.gs-head')];
const fgs=document.getElementById('f-gs'), fc=document.getElementById('f-corps'), fq=document.getElementById('f-q'), cnt=document.getElementById('count');
const seg=document.getElementById('f-status'); let status='';
const sGs=new Set(), sC=new Set();
rows.forEach(r=>{ if(r.dataset.gs) sGs.add(r.dataset.gs); (r.dataset.corps||'').split(';').forEach(c=>{ if(c.trim()) sC.add(c.trim()); }); });
const fill=(sel,vals)=>[...vals].sort((a,b)=>a.localeCompare(b,'fr')).forEach(v=>{ const o=document.createElement('option'); o.value=v; o.textContent=v; sel.appendChild(o); });
fill(fgs,sGs); fill(fc,sC);
const norm=s=>(s||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();
function filter(){
  let n=0; const q=norm(fq.value), visibleGs=new Set();
  rows.forEach(r=>{
    const st=r.classList.contains('row-retenu')?'retenu':(r.classList.contains('row-ferme')?'ferme':'vacant');
    const ok=(!status||st===status)&&(!fgs.value||r.dataset.gs===fgs.value)
      &&(!fc.value||(r.dataset.corps||'').split(';').map(s=>s.trim()).includes(fc.value))
      &&(!q||norm(r.textContent).includes(q));
    r.hidden=!ok; if(ok){ n++; visibleGs.add(r.dataset.gs); }
  });
  heads.forEach(h=>h.hidden=!visibleGs.has(h.dataset.gs));
  cnt.textContent=n;
}
seg.addEventListener('click',e=>{ const b=e.target.closest('button'); if(!b) return; status=b.dataset.v; seg.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b)); filter(); });
[fgs,fc,fq].forEach(el=>el.addEventListener('input',filter));
filter();
})();
</script>
</body></html>"""
    return (html.replace("%%NAVCSS%%", _NAV_CSS).replace("%%BANNER%%", _CFDT_BANNER)
                .replace("%%NAV%%", _nav("resultats.html", has_resultats=True))
                .replace("%%CAMPAIGN%%", campaign).replace("%%TOTAL%%", str(total))
                .replace("%%RET%%", str(n_ret)).replace("%%VAC%%", str(n_vac))
                .replace("%%PCT%%", str(pct))
                .replace("%%FER%%", f" · {n_fer} fermé(s) par additif, non comptés" if n_fer else "").replace("%%BODY%%", "\n".join(rows)))


# ── Page informations pratiques ──────────────────────────────────────────────

def _render_info(campaign: str, has_resultats: bool, info: dict | None = None) -> str:
    from .campaign_info import DEFAULT_INFO, parse_contacts, parse_notes
    info = {**DEFAULT_INFO, **(info or {})}

    etat = "est ouverte" if info["statut"] == "ouverte" else "est close"
    message_html = ""
    if info["message"]:
        message_html = ('<div class="alert-box" style="font-size:14px;color:#333">'
                        + _e(info["message"]).replace("\n", "<br>") + "</div>")

    contacts, _ = parse_contacts(info["contacts"])
    contacts_html = "\n".join(
        f'      <li><strong>{_e(corps)}</strong> : '
        + " et ".join(f'<a href="mailto:{_e(mail)}">{_e(nom)}</a>' for nom, mail in people)
        + "</li>"
        for corps, people in contacts
    )
    notes, _ = parse_notes(info["notes"])
    notes_html = "\n".join(
        f'      <li><a href="{_e(url)}" target="_blank" rel="noopener">{_e(label)} ↗</a></li>'
        for label, url in notes
    )

    return f"""<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CFDT — Informations pratiques</title>
<link rel="stylesheet" href="assets/styles.css">
{_NAV_CSS}
<style>
.info-section {{ background:#fff;border-radius:14px;box-shadow:0 2px 12px rgba(0,0,0,.06);
  padding:22px 28px;margin-bottom:18px; }}
.info-section h2 {{ font-size:17px;color:#E7591C;margin:0 0 12px;border-bottom:2px solid #E7591C;padding-bottom:6px; }}
.info-section h3 {{ font-size:14px;color:#444;margin:16px 0 6px; }}
.info-section p {{ margin:0 0 10px;line-height:1.65; }}
.info-section ul {{ margin:6px 0 12px;padding-left:20px;line-height:1.7; }}
.info-section a {{ color:#E7591C; }}
.info-section a:hover {{ text-decoration:underline; }}
.alert-box {{ background:#fff8f5;border:1.5px solid rgba(231,89,28,.3);border-radius:10px;
  padding:12px 16px;margin-bottom:12px;font-size:13px;color:#555; }}
</style>
</head><body>
{_CFDT_BANNER}
{_nav("info.html", has_resultats)}
<main class="container" style="max-width:860px">

  <h1 style="margin:18px 0 16px;font-size:22px;">Informations pratiques — {campaign}</h1>

  <div class="info-section">
    <h2>Ouverture de la campagne et échéances</h2>
    <p>La campagne de mobilité <strong>{campaign}</strong> {etat}.</p>
    {message_html}
    <ul>
      <li><strong>Date limite pour candidater et pour modifier ou annuler une candidature :</strong>
        {_e(info["date_limite"])}</li>
      <li><strong>Avis des services sur les candidatures (date limite dans le SIRH) :</strong>
        {_e(info["date_avis"])}</li>
      <li><strong>Publication des résultats :</strong> {_e(info["date_resultats"])}</li>
    </ul>
    <p>Les fiches de postes peuvent être consultées à partir du <strong>SIRH</strong>.</p>
    <div class="alert-box">
      Le dépôt des candidatures s'effectue via l'application <strong>"SIRH - Agents"</strong>
      accessible sur la page d'accueil de Bravo Victor en intranet. L'accès s'effectue sur
      Bravo Victor (menu "applications") grâce au login et mot de passe Angélique, en cliquant
      sur l'icône "SIRH - Agents".
    </div>
    <p>
      Pour plus d'information sur le nouveau portail SIRH :
      <a href="https://bv.sigp.aviation-civile.gouv.fr/carriere/le-sirh/portail-agent-du-sirh-hr4you"
         target="_blank" rel="noopener">Page dédiée sur Bravo Victor ↗</a>
    </p>
    <p>
      <a href="https://bv.sigp.aviation-civile.gouv.fr/sites/default/files/atoms/files/guide_utilisateur_agent_for_you.pdf"
         target="_blank" rel="noopener">📥 Guide utilisateur SIRH (PDF) ↗</a>
    </p>
  </div>

  <div class="info-section">
    <h2>Informations complémentaires</h2>
    <p>La date limite de remise d'un <strong>dossier social</strong> auprès de l'assistante sociale
    et/ou d'un <strong>dossier médical</strong> auprès de la médecine du travail, associé à une
    candidature, est identique à la date limite de remise des candidatures.</p>
    <p>Le service DSNA/SDRH rappelle aux candidats relevant des corps de la navigation aérienne
    (<strong>ICNA, IESSA et TSEEAC</strong>) que l'annulation d'une candidature, au-delà de la
    date limite de candidature, entraînera l'annulation de l'ensemble des candidatures de l'agent.</p>
  </div>

  <div class="info-section">
    <h2>Candidatures par mail (en cas de difficultés techniques)</h2>
    <p>En cas de difficultés techniques ou d'impossibilité à postuler via SIRH uniquement,
    les candidatures par mail seront acceptées aux adresses suivantes :</p>
    <ul>
{contacts_html}
    </ul>
  </div>

  <div class="info-section">
    <h2>Notes de gestion</h2>
    <ul>
{notes_html}
    </ul>
    <p style="margin-top:14px;padding-top:12px;border-top:1px solid #eee;color:#E7591C;font-weight:600">
      N'hésitez pas à nous contacter, par mail ou à venir à une de nos permanences
      pour toute interrogation ou demande mobilité !
    </p>
  </div>

</main>
<footer>© CFDT Aviation Civile</footer>
</body></html>"""


# ── Point d'entrée ────────────────────────────────────────────────────────────

def generate_static_site(
    df_ave:       pd.DataFrame,
    df_csp:       pd.DataFrame | None,
    df_complet:   pd.DataFrame | None,
    outdir:       str,
    campaign:     str,
    ave_to_url:   dict | None = None,
    assets_src:   str | None  = None,
    df_sirh:      pd.DataFrame | None = None,
    info:         dict | None = None,
) -> list[str]:
    """
    Génère le site statique dans `outdir`.
    Retourne la liste des fichiers créés.
    """
    out   = Path(outdir)
    files = []
    campaign = _e(campaign)

    # CSS
    css_dest = out / "assets" / "styles.css"
    if assets_src and Path(assets_src).exists():
        css_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(assets_src, css_dest)
    else:
        _write(css_dest, _DEFAULT_CSS)
    files.append(str(css_dest))

    # Accueil
    has_res = df_complet is not None and not df_complet.empty
    p = out / "index.html"
    _write(p, _render_home(campaign, has_res))
    files.append(str(p))

    # Page informations pratiques
    p = out / "info.html"
    _write(p, _render_info(campaign, has_res, info))
    files.append(str(p))

    # Préparer ave_url (sera complété depuis CSP ci-dessous)
    ave_url = dict(ave_to_url) if ave_to_url else {}

    # Offres CSP — traiter EN PREMIER pour remplir ave_url avant le tableau
    if df_csp is not None and not df_csp.empty:
        keep = ["titre","url","numero_ave","employeur","localisation","domaine",
                "teletravail","type_contrat","experience","remuneration",
                "missions","profil_recherche","description","contacts"]
        for c in keep:
            if c not in df_csp.columns:
                df_csp[c] = ""
        # Normalisation des noms d'employeurs (ASCII only pour robustesse)
        def _norm_emp(s):
            import unicodedata
            s = str(s).strip()
            # Supprimer les accents pour la comparaison
            s_ascii = ''.join(
                c for c in unicodedata.normalize('NFD', s.lower())
                if unicodedata.category(c) != 'Mn'
            )
            if "(sg)" in s_ascii or "secretariat general" in s_ascii:
                return "SG"
            if "(dta)" in s_ascii or "transport aerien" in s_ascii:
                return "DTA"
            if "dgac" in s_ascii or "aviation civile" in s_ascii:
                return "DGAC"
            return s
        df_csp = df_csp.copy()
        df_csp["employeur"] = df_csp["employeur"].apply(_norm_emp)
        p = out / "data" / "offres_csp.json"
        _write_json(_records(df_csp[keep]), p)
        files.append(str(p))
        # Construire ave_to_url depuis CSP si pas encore fourni
        # (la clé doit être normalisée : "DGAC-AVE-127265-CAT-A" → "127265")
        if not ave_url and "numero_ave" in df_csp.columns and "url" in df_csp.columns:
            for _, r in df_csp.iterrows():
                raw = str(r.get("numero_ave","") or "")
                k = re.sub(r'[^\d]', '', raw).lstrip("0")
                u = str(r.get("url","") or "")
                if k and u and u.lower() != 'nan':
                    ave_url[k] = u

    # Tableau filtrable — rendu APRÈS que ave_url soit rempli
    p = out / "tableau.html"
    _write(p, _render_tableau(df_ave, ave_url, campaign, has_res))
    files.append(str(p))

    # JSON AVE
    p = out / "data" / "ave.json"
    _write_json(_records(df_ave), p)
    files.append(str(p))

    # Offres combinées CSP + SIRH → offres.html
    has_sirh = df_sirh is not None and not df_sirh.empty
    combined = _build_combined_offers(
        df_csp  if (df_csp  is not None and not df_csp.empty)  else None,
        df_sirh if has_sirh else None,
    )
    if combined:
        p = out / "data" / "offres.json"
        _write_json(combined, p)
        files.append(str(p))
        p = out / "offres.html"
        _write(p, _render_offres(has_sirh=has_sirh, has_resultats=has_res))
        files.append(str(p))
    elif df_csp is not None and not df_csp.empty:
        # Pas de SIRH mais CSP présent : page sans filtre source
        p = out / "offres.html"
        _write(p, _render_offres(has_sirh=False, has_resultats=has_res))
        files.append(str(p))

    # Résultats CDM
    if has_res:
        p = out / "resultats.html"
        _write(p, _render_resultats(df_complet, campaign))
        files.append(str(p))
        p = out / "data" / "resultats.json"
        _write_json(_records(df_complet), p)
        files.append(str(p))

    # En-têtes de sécurité + noindex (Netlify)
    p = out / "_headers"
    _write(p, _NETLIFY_HEADERS)
    files.append(str(p))

    return files


# ── CSS par défaut (fallback) ─────────────────────────────────────────────────

_DEFAULT_CSS = """:root{--cfdt:#E7591C;--cfdt-dark:#cc4711;--ink:#222;--muted:#6A6A6A;
--bg:#fff;--line:#E9E9E9;--radius:16px;--shadow:0 2px 14px rgba(0,0,0,.06);}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:400 16px/1.55 system-ui,sans-serif;}
a{color:var(--cfdt);text-decoration:none}a:hover{text-decoration:underline}
.header{position:sticky;top:0;z-index:50;display:flex;align-items:center;
justify-content:space-between;gap:16px;padding:14px 24px;background:var(--cfdt);color:#fff;}
.brand{font-weight:800}.container{max-width:1180px;margin:0 auto;padding:22px}
h1{font-weight:800;font-size:28px;margin:4px 0 14px}
.small{font-size:13px;color:var(--muted)}
.controls{display:flex;flex-wrap:wrap;gap:10px;margin:6px 0 16px}
.controls input,.controls select{padding:10px 12px;min-width:180px;border:1px solid var(--line);border-radius:12px}
.btn{display:inline-flex;align-items:center;padding:10px 14px;border-radius:999px;
border:1px solid var(--cfdt);color:#fff;background:var(--cfdt);font-weight:700;cursor:pointer;text-decoration:none;}
.btn.secondary{background:#fff;color:var(--cfdt)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.card{background:#fff;border:1px solid var(--line);border-radius:var(--radius);
box-shadow:var(--shadow);padding:16px;}
.badge{display:inline-flex;padding:4px 10px;border-radius:999px;
background:rgba(231,89,28,.08);border:1px solid rgba(231,89,28,.25);
color:var(--cfdt);font-weight:800;font-size:12px;}
.tablewrap{overflow-x:auto}.table{border-collapse:collapse;width:100%}
.table th,.table td{border:1px solid var(--line);padding:8px;vertical-align:top;font-size:14px}
.table th{background:#fafafa;font-weight:700}
.modal{position:fixed;inset:0;display:none;align-items:center;justify-content:center;
background:rgba(0,0,0,.45);padding:24px}.modal.open{display:flex}
.panel{background:#fff;width:min(900px,100%);max-height:92vh;overflow:auto;
border-radius:20px;padding:20px 24px;position:relative}
.close{position:absolute;top:16px;right:20px;cursor:pointer;font-size:20px;font-weight:800;color:var(--muted)}
.panel h4{margin:1rem 0 .4rem;font-size:14px;color:#555}
.panel h4:first-of-type{margin-top:.5rem}
footer{padding:28px;text-align:center;color:var(--muted);border-top:1px solid var(--line);margin-top:24px}
@media(max-width:720px){.grid{grid-template-columns:1fr}
.controls input,.controls select{min-width:unset;width:100%}}"""
