# Veille articles

Toutes les 15 minutes, une vérification lit les flux RSS de ces sites et envoie une notification (via l'application ntfy) pour chaque nouvel article :

- Zone Militaire (Opex360)
- OpexNews
- TWZ
- Le Grand Continent

## Comment ça marche

- **Le rythme vient de Google.** Le projet Apps Script « Veille géopolitique » (sur script.google.com) demande à GitHub de lancer la vérification toutes les 15 minutes. Google respecte cet horaire, alors que GitHub, seul, saute souvent des passages.
- `veille.py` lit les flux et envoie les notifications.
- `.github/workflows/veille.yml` lance `veille.py` à chaque demande de Google, et une fois par heure en secours si Google ne répond plus.
- `seen.json` garde la liste des articles déjà vus. Il est mis à jour automatiquement.
- Le nom du sujet ntfy est stocké dans le secret GitHub `NTFY_TOPIC` (Settings → Secrets and variables → Actions). La clé qui permet à Google de lancer GitHub est rangée dans les propriétés du script Google, sous le nom `GITHUB_TOKEN`. Aucune des deux n'apparaît dans un fichier.

## Modifier

- **Ajouter ou retirer un site** : modifie la liste `FEEDS` en haut de `veille.py`. Sur la plupart des sites WordPress, le flux est l'adresse du site suivie de `/feed/`.
- **Changer la fréquence** : dans le script Google, modifie `FREQUENCE_MINUTES` (1, 5, 10, 15 ou 30), enregistre, puis exécute la fonction `installer`.
- **Mettre en pause** : dans le script Google, exécute `arreter` (GitHub continue alors une fois par heure). Pour tout arrêter, désactive aussi le workflow ici : onglet Actions → Veille articles → bouton « … » → Disable workflow.
- **Lancer une vérification tout de suite** : onglet Actions → Veille articles → Run workflow.
- **Recevoir une notification de test** : même chemin, en cochant « Envoyer seulement une notification de test ».
