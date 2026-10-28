# Veille articles

Toutes les 15 minutes, GitHub lit les flux RSS de ces sites et envoie une notification (via l'application ntfy) pour chaque nouvel article :

- Zone Militaire (Opex360)
- OpexNews
- TWZ
- Le Grand Continent

## Comment ça marche

- `veille.py` lit les flux et envoie les notifications.
- `.github/workflows/veille.yml` lance le script toutes les 15 minutes (à :07, :22, :37 et :52).
- `seen.json` garde la liste des articles déjà vus. Il est mis à jour automatiquement.
- Le nom du sujet ntfy est stocké dans le secret `NTFY_TOPIC` (Settings → Secrets and variables → Actions). Il n'apparaît dans aucun fichier.

GitHub ne garantit pas l'horaire : quand ses serveurs sont chargés, certains passages sont retardés ou sautés. L'écart réel entre deux vérifications peut donc dépasser 15 minutes.

## Modifier

- **Ajouter ou retirer un site** : modifie la liste `FEEDS` en haut de `veille.py`. Sur la plupart des sites WordPress, le flux est l'adresse du site suivie de `/feed/`.
- **Changer la fréquence** : modifie la ligne `cron` dans `.github/workflows/veille.yml`, par exemple `"0 * * * *"` pour toutes les heures.
- **Mettre en pause** : onglet Actions → Veille articles → bouton « … » → Disable workflow.
- **Lancer une vérification tout de suite** : onglet Actions → Veille articles → Run workflow.
