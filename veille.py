#!/usr/bin/env python3
"""
Veille d'articles : lit des flux RSS et envoie une notification (via ntfy)
pour chaque nouvel article publié depuis le passage précédent.

Utilisation :
    NTFY_TOPIC=mon-sujet-secret python3 veille.py         # passage normal
    NTFY_TOPIC=mon-sujet-secret python3 veille.py --test  # notification de test

Sans NTFY_TOPIC, les nouveaux articles sont simplement affichés dans le terminal.
Aucune bibliothèque à installer : uniquement Python 3.
"""

import html
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# --- Configuration -----------------------------------------------------------

# Sites surveillés : "Nom affiché dans la notification": "adresse du flux RSS"
FEEDS = {
    "Zone Militaire (Opex360)": "https://www.opex360.com/feed/",
    "OpexNews": "https://opexnews.fr/feed/",
    "TWZ": "https://www.twz.com/feed/",
    "Le Grand Continent": "https://legrandcontinent.eu/fr/feed/",
}

# Fichier où sont mémorisés les articles déjà vus (créé automatiquement)
STATE_FILE = Path(__file__).with_name("seen.json")

# Notifications ntfy (https://ntfy.sh)
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
NTFY_TOKEN = os.environ.get("NTFY_TOKEN", "").strip()  # facultatif

# Au-delà de ce nombre de nouveaux articles d'un coup pour un même site,
# on envoie un seul message récapitulatif au lieu d'une rafale.
MAX_NOTIFS_PAR_SITE = 3

# Nombre d'identifiants d'articles gardés en mémoire par site
MEMOIRE_PAR_SITE = 300

USER_AGENT = "Mozilla/5.0 (compatible; VeilleRSS/1.0)"
TIMEOUT = 30  # secondes

ATOM = "{http://www.w3.org/2005/Atom}"


# --- Lecture des flux ---------------------------------------------------------

def telecharger(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as reponse:
        return reponse.read()


def _texte(element, chemin):
    valeur = element.findtext(chemin)
    return html.unescape(valeur).strip() if valeur else ""


def lire_articles(contenu_xml):
    """Renvoie la liste des articles du flux (du plus récent au plus ancien)."""
    racine = ET.fromstring(contenu_xml)
    articles = []

    items = racine.findall("./channel/item")
    if items:  # Flux RSS 2.0
        for item in items:
            titre = _texte(item, "title")
            lien = _texte(item, "link")
            ident = _texte(item, "guid") or lien or titre
            if ident:
                articles.append({"id": ident, "titre": titre, "lien": lien})
        return articles

    for entree in racine.findall(f"{ATOM}entry"):  # Flux Atom
        titre = _texte(entree, f"{ATOM}title")
        lien = ""
        for el in entree.findall(f"{ATOM}link"):
            if el.get("rel", "alternate") == "alternate" and el.get("href"):
                lien = el.get("href")
                break
        ident = _texte(entree, f"{ATOM}id") or lien or titre
        if ident:
            articles.append({"id": ident, "titre": titre, "lien": lien})
    return articles


# --- Notifications --------------------------------------------------------------

def envoyer(titre, message, lien=""):
    """Envoie une notification. Renvoie True si elle est bien partie."""
    if not NTFY_TOPIC:
        print(f"    -> {titre} | {message} {lien}".rstrip())
        return True

    donnees = {"topic": NTFY_TOPIC, "title": titre, "message": message}
    if lien:
        donnees["click"] = lien
    entetes = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if NTFY_TOKEN:
        entetes["Authorization"] = f"Bearer {NTFY_TOKEN}"

    req = urllib.request.Request(
        NTFY_SERVER,
        data=json.dumps(donnees).encode("utf-8"),
        headers=entetes,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as reponse:
            return 200 <= reponse.status < 300
    except Exception as exc:  # réseau, serveur indisponible…
        print(f"    !! notification non envoyée : {exc}", file=sys.stderr)
        return False


def notifier(nom_site, nouveaux):
    """Notifie les nouveaux articles d'un site. Renvoie les identifiants notifiés."""
    if len(nouveaux) <= MAX_NOTIFS_PAR_SITE:
        notifies = set()
        # Du plus ancien au plus récent : le plus récent arrive en dernier
        for article in reversed(nouveaux):
            if envoyer(nom_site, article["titre"] or article["lien"], article["lien"]):
                notifies.add(article["id"])
        return notifies

    liste = "\n".join(f"• {a['titre']}" for a in nouveaux[:10])
    if len(nouveaux) > 10:
        liste += f"\n… et {len(nouveaux) - 10} autre(s)"
    titre = f"{nom_site} : {len(nouveaux)} nouveaux articles"
    if envoyer(titre, liste, nouveaux[0]["lien"]):
        return {a["id"] for a in nouveaux}
    return set()


# --- Mémoire des articles déjà vus ----------------------------------------------

def charger_etat():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            print("Fichier seen.json illisible : il sera recréé.", file=sys.stderr)
    return {}


def sauver_etat(etat):
    temporaire = STATE_FILE.with_suffix(".tmp")
    temporaire.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")
    temporaire.replace(STATE_FILE)


# --- Programme principal ------------------------------------------------------

def verifier_site(nom, url, etat):
    """Vérifie un site et met à jour etat. Renvoie False en cas d'erreur de lecture."""
    try:
        articles = lire_articles(telecharger(url))
    except Exception as exc:
        print(f"[{nom}] erreur de lecture du flux : {exc}", file=sys.stderr)
        return False

    ids_actuels = [a["id"] for a in articles]
    deja_vus = etat.get(url)

    if deja_vus is None:
        # Premier passage pour ce site : on mémorise sans rien notifier,
        # sinon tu recevrais d'un coup tous les articles déjà en ligne.
        etat[url] = ids_actuels[:MEMOIRE_PAR_SITE]
        print(f"[{nom}] initialisé : {len(articles)} article(s) déjà en ligne, aucune notification")
        return True

    vus = set(deja_vus)
    nouveaux = [a for a in articles if a["id"] not in vus]
    notifies = notifier(nom, nouveaux) if nouveaux else set()

    # Un article dont la notification a échoué n'est pas marqué comme vu :
    # il sera retenté au prochain passage.
    gardes = [i for i in ids_actuels if i in vus or i in notifies]
    anciens = [i for i in deja_vus if i not in set(gardes)]
    etat[url] = (gardes + anciens)[:MEMOIRE_PAR_SITE]

    echecs = len(nouveaux) - len(notifies)
    message = f"[{nom}] {len(nouveaux)} nouvel(s) article(s)"
    if echecs:
        message += f", {echecs} notification(s) à retenter"
    print(message)
    return True


def main():
    if "--test" in sys.argv:
        if not NTFY_TOPIC:
            sys.exit("Définis d'abord NTFY_TOPIC pour tester l'envoi.")
        ok = envoyer("Veille articles", "Notification de test : tout fonctionne !")
        print("Notification de test envoyée." if ok else "Échec de l'envoi.")
        sys.exit(0 if ok else 1)

    print(f"Vérification du {datetime.now():%d/%m/%Y à %H:%M}")
    if not NTFY_TOPIC:
        print("(NTFY_TOPIC non défini : affichage dans le terminal uniquement)")

    etat = charger_etat()
    reussites = sum(verifier_site(nom, url, etat) for nom, url in FEEDS.items())

    # On oublie les sites retirés de la configuration
    for url in list(etat):
        if url not in FEEDS.values():
            del etat[url]
    sauver_etat(etat)

    if reussites == 0:
        sys.exit("Aucun flux n'a pu être lu.")


if __name__ == "__main__":
    main()
