# Conventions de Développement - Alfred

## 1. Style de Code Python
- Python 3.11+ (utilise `match/case`, `dataclasses`, `typing` natif : `list[str]`, `dict[str, Any]`, `tuple[int, int]`, etc.).
- Respect des principes PEP 8 pour le formatage.
- Fonctions courtes à responsabilité unique (Single Responsibility Principle).
- Commentaires clairs en français pour documenter l'intention métier, docstrings sur toutes les classes et méthodes publiques.

## 2. Typage et Robustesse
- Tous les modèles de configuration doivent être définis sous forme de `dataclass` typées dans `src/alfred/core/models.py`.
- Tolérance aux pannes : un fichier `.toml` corrompu ou contenant une commande inconnue doit lever un avertissement dans les logs sans faire planter l'application au démarrage.

## 3. Découplage Matériel & OS
- Les appels directs à l'API Windows (via `ctypes.windll.user32`) sont encapsulés exclusivement dans `src/alfred/core/mouse.py`.
- Le moteur de commandes ne doit pas manipuler de handles Windows bruts.

## 4. Stratégie de Tests
- Utiliser `pytest` pour les tests unitaires.
- Ne pas tester les hooks réels lors des tests automatisés (mocker les fonctions de simulation de frappe ou de souris).
- Tester rigoureusement :
  - Le chargement et la validation de tous les fichiers TOML.
  - La logique de transition d'états et de modes.
  - Les calculs de coordonnées de cases de la grille d'écran.
  - La résolution des commandes et des toggles d'état.
