# Storcube Battery Monitor

Intégration pour les batteries de balcon **STORCUBE S1000**, via l'API cloud
Baterway. Prend en charge les stacks de plusieurs modules : chaque batterie
devient un appareil distinct.

## Ce que vous obtenez

**Par batterie** — niveau de charge, température, capacité restante, état,
numéro de série, version de firmware.

**Pour le stack** — puissance solaire par MPPT, puissance de sortie mesurée,
charge/décharge de la batterie, quatre compteurs d'énergie compatibles avec le
tableau de bord Énergie, seuil de décharge et état de fonctionnement.

**En contrôle** — consigne de puissance de sortie (0–800 W) et seuil de
décharge (0–100 %), plus trois services dont une vérification de firmware qui
retourne ses résultats.

## Avant d'installer

Il vous faut le **compte de l'application mobile STORCUBE** — l'adresse e-mail
complète et son mot de passe — ainsi que le numéro de série de la batterie
maître. Ce ne sont ni les identifiants de Home Assistant, ni ceux d'un broker
MQTT.

L'intégration est en `cloud_push` : tout transite par `baterway.com`. Aucune
communication locale n'est possible, et une coupure Internet rend les entités
indisponibles. L'intégration MQTT de Home Assistant est facultative.

## Après l'installation

*Paramètres → Appareils et services → Ajouter une intégration →
« Storcube Battery Monitor »*

Une batterie ne peut être ajoutée qu'une fois. Si vous migrez depuis une
version 1.2.x, **supprimez vos entrées existantes avant d'en recréer une** :
les anciennes n'ont pas d'identifiant unique.

## Bon à savoir

Les esclaves d'un stack n'exposent ni solaire, ni sortie, ni seuil — l'API ne
remonte ces grandeurs que pour la maître. C'est normal, pas un défaut de
configuration.

Pour le tableau de bord Énergie, n'utilisez que `Énergie solaire totale` en
production : ajouter les compteurs 1 et 2 en plus compterait deux fois.

---

Documentation complète, dépannage et sémantique de l'API dans le
[README](https://github.com/jon7119/storcube_Ha#readme).
