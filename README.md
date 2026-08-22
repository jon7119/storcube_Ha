# Storcube Battery Monitor

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![version](https://img.shields.io/badge/version-1.3.6-blue.svg)](https://github.com/xez7082/storcube_Ha/releases)

Intégration Home Assistant pour les batteries de balcon **STORCUBE S1000**,
via l'API cloud Baterway.

Prend en charge les stacks de plusieurs modules : chaque batterie devient un
appareil distinct, avec ses propres capteurs.

---

## Fonctionnement

L'intégration ne parle pas directement à la batterie. Elle passe par le service
cloud de Baterway, comme l'application mobile STORCUBE.

- Un **WebSocket** maintient une connexion permanente et reçoit l'état temps
  réel de chaque batterie : charge, puissance onduleur, entrées solaires,
  température, capacité restante.
- Une **boucle REST** interroge périodiquement l'état de sortie, le seuil de
  décharge et le firmware.

Les deux flux alimentent un coordinateur unique qui les fusionne par batterie,
le WebSocket étant prioritaire car plus frais.

Si l'intégration MQTT de Home Assistant est présente, l'état est également
republié sous `storcube/<equipId>/…` pour les automatisations externes. Elle
est **facultative** : sans elle, tout fonctionne, il n'y a simplement pas de
republication.

> **`iot_class` : `cloud_push`.** Tout transite par `baterway.com`. Aucune
> communication locale n'est possible en l'état : une coupure Internet rend
> les entités indisponibles.

---

## Installation

### Via HACS

1. HACS → Intégrations → menu ⋮ → **Dépôts personnalisés**
2. Ajoutez `https://github.com/xez7082/storcube_Ha`, catégorie *Intégration*
3. Recherchez « Storcube Battery Monitor », téléchargez
4. Redémarrez Home Assistant

> N'ajoutez pas deux dépôts HACS pointant sur le même domaine `storcube_ha` :
> la mise à jour de l'un écraserait les fichiers de l'autre.

### Manuelle

Copiez `custom_components/storcube_ha/` dans votre dossier
`config/custom_components/`, puis redémarrez Home Assistant.

---

## Configuration

*Paramètres → Appareils et services → Ajouter une intégration →
« Storcube Battery Monitor »*

| Champ | Valeur |
|---|---|
| **Identifiant de l'équipement** | Numéro de série de la batterie **maître**, visible dans l'application |
| **Identifiant de connexion** | Compte STORCUBE — **l'adresse e-mail complète** si vous vous êtes inscrit ainsi |
| **Mot de passe** | Mot de passe du même compte |
| **Code application** | `Storcube` (valeur par défaut) |

Ce sont les identifiants de l'**application mobile STORCUBE**, pas ceux de Home
Assistant ni d'un broker MQTT. Le domaine `baterway.com` correspond au backend
historique de la marque.

Une batterie ne peut être ajoutée qu'une fois : l'identifiant d'équipement sert
de clé d'unicité.

### Options

L'intervalle d'interrogation REST est réglable de **15 à 600 secondes**
(30 s par défaut).

Pour modifier vos identifiants, utilisez **Reconfigurer** sur l'entrée — pas
les options. En cas de mot de passe changé côté Baterway, Home Assistant
proposera de lui-même une réauthentification.

---

## Entités

### Communes à toutes les batteries du stack

| Entité | Unité | Source |
|---|---|---|
| Niveau batterie | % | WebSocket |
| Température batterie | °C | WebSocket |
| Capacité batterie | Wh | WebSocket |
| État batterie | — | WebSocket |
| Numéro de série | — | WebSocket |
| Version firmware | — | API firmware |

### Batterie maître uniquement

Ces grandeurs décrivent le stack entier ou proviennent de l'API REST, qui
n'interroge que la maître. Les créer sur un esclave produirait des entités
vides — ou, pour les compteurs d'énergie, un double comptage.

| Entité | Unité | Remarque |
|---|---|---|
| Puissance batterie | W | Charge/décharge, **positive à la charge**. Calculée : solaire − onduleur |
| Puissance de sortie | W | Puissance mesurée vers l'onduleur |
| Consigne de sortie | W | Réglage configuré. *Désactivée par défaut* |
| Puissance solaire 1 / 2 | W | Une entrée par MPPT |
| Énergie solaire 1 / 2 / totale | kWh | Intégrées, restaurées au redémarrage |
| Énergie de sortie | kWh | Intégrée sur la puissance **mesurée** |
| Seuil batterie · Niveau de réserve | % | |
| Modèle · Type de sortie | — | |
| État de fonctionnement · État de connexion | — | |
| Firmware | — | Résumé de mise à jour, avec notes de version en attributs |

### Contrôles

| Entité | Plage |
|---|---|
| Puissance de sortie | 0 – 800 W |
| Seuil de décharge | 0 – 100 % |

Ces consignes s'appliquent au stack et ne sont créées que pour la maître.

### Capteur binaire

`Connexion` — état de liaison de la batterie. La plateforme existe mais n'est
pas activée par défaut : ajoutez `Platform.BINARY_SENSOR` à `PLATFORMS` dans
`__init__.py` pour l'utiliser.

---

## Tableau de bord Énergie

**Production solaire** → `Énergie solaire totale` **uniquement**. N'ajoutez pas
`Énergie solaire 1` et `2` en plus, vous compteriez deux fois.

**Batterie** → le tableau de bord attend deux compteurs distincts, entrant et
sortant, que l'API ne fournit pas. Créez-les avec deux capteurs *Intégrale de
Riemann* à partir de `Puissance batterie`, l'un filtré sur les valeurs
positives, l'autre sur les négatives.

**Énergie de sortie** ne va dans aucune des deux cases : elle représente ce qui
part vers l'onduleur, donc de l'autoconsommation, pas un échange avec le
réseau. Gardez-la comme capteur informatif.

---

## Services

| Service | Description |
|---|---|
| `storcube_ha.set_power` | Consigne de puissance de sortie (0–800 W) |
| `storcube_ha.set_threshold` | Seuil de décharge (0–100 %) |
| `storcube_ha.check_firmware` | Interroge l'API et **retourne** versions et notes de version |

Le champ `device_id` est facultatif : il n'est requis que si plusieurs entrées
sont configurées. En cas d'ambiguïté, le service lève une erreur explicite
plutôt que d'agir sur une batterie au hasard.

```yaml
action: storcube_ha.check_firmware
response_variable: firmware
```

---

## Dépannage

Activez les journaux détaillés :

```yaml
logger:
  default: warning
  logs:
    custom_components.storcube_ha: debug
```

| Message | Signification |
|---|---|
| `Token StorCube renouvelé` | Authentification réussie |
| `WebSocket StorCube connecté` | Liaison temps réel établie |
| `Abonnement WebSocket envoyé` | Trame `reportEquip` transmise |
| `Nouvelle batterie StorCube détectée : …` | Appareil et entités créés |
| `Trame WebSocket sans batterie : clés=…` | Format inattendu — ouvrez un ticket avec cette ligne |
| `Boucle REST en échec …` | API injoignable ; réessai avec délai croissant |
| `Champ de seuil retenu pour l'API : …` | Variante de paramètre acceptée par l'API |

### Problèmes courants

**« Authentification invalide » alors que le compte fonctionne.**
L'API répond en HTTP 200 même avec de mauvais identifiants ; c'est le champ
`code` de la réponse qui fait foi. Vérifiez d'abord que le compte fonctionne
dans l'application mobile, et utilisez l'**adresse e-mail complète** plutôt
qu'un pseudonyme.

**Seules les valeurs REST apparaissent, les autres restent `unknown`.**
Si le niveau de charge, la puissance, la température et le solaire manquent
alors que le seuil et le type de sortie s'affichent, le WebSocket ne délivre
rien. Vérifiez que le compte n'est pas déjà connecté ailleurs : l'API tolère
mal plusieurs sessions simultanées.

**Les entités d'un esclave restent vides.**
C'est attendu pour le solaire, la sortie, le seuil et le modèle : l'API ne les
remonte que pour la maître.

**Journaux saturés au démarrage.**
La boucle REST applique un backoff exponentiel et ne logue qu'un avertissement
par série d'échecs. Si vous voyez plus que cela, vous avez probablement
plusieurs entrées configurées pour la même batterie.

---

## Sémantique de l'API

L'API Baterway n'est pas documentée. Ce tableau résume ce que l'observation a
permis d'établir — il vaut avertissement autant que documentation.

| Champ | Signification |
|---|---|
| `outputPower` (REST) | Consigne de sortie configurée, constante |
| `invPower` / `totalInvPower` | Puissance réellement délivrée à l'onduleur |
| `pv1power` / `pv2power` | Entrées solaires, par MPPT |
| `soc` | Niveau de charge en % |
| `capacity` | Énergie **restante** en Wh, pas la capacité maximale |
| `reserved` | Seuil de décharge |
| `fgOnline` | Absent des trames observées |
| `lastBigVersion` | Version **installée** *(contre-intuitif)* |
| `currentBigVersion` | Version **disponible** *(contre-intuitif)* |

Les trames WebSocket arrivent sous la forme
`{"<equipId>": {"totalPv1power": …, "list": [{…}]}}`. Les totaux portés par le
conteneur décrivent le stack entier et ne sont attribués qu'à la maître.

Le paramètre de réglage du seuil est accepté sous plusieurs noms de champ selon
les firmwares. L'intégration essaie les variantes connues, puis mémorise celle
qui fonctionne.

---

## Limites connues

- Aucune communication locale. L'intégration dépend entièrement du cloud
  Baterway, dont la disponibilité est variable.
- Le mapping `lastBigVersion` / `currentBigVersion` reste à confirmer sur une
  installation disposant réellement d'une mise à jour en attente.
- Les esclaves n'exposent ni solaire, ni sortie, ni seuil.
- Testé sur un stack de deux S1000 en firmware 1.1.0. Les retours sur d'autres
  configurations sont les bienvenus.

---

## Historique

La **v1.3.6** est une refonte complète de l'architecture interne : coordinateur
unique, suppression des connexions en double, correction du plantage
`'StorCubeDataUpdateCoordinator' object has no attribute 'get'`, arrêt de
l'écrasement du tableau de bord Lovelace, fiabilisation des compteurs
d'énergie, support multi-batteries.

**Si vous migrez depuis une 1.2.x**, consultez les
[notes de version](https://github.com/xez7082/storcube_Ha/releases) : trois
opérations manuelles sont nécessaires, dont la suppression des anciennes
entrées de configuration.

Pour l'historique antérieur, voir le dépôt d'origine
[jon7119/storcube_Ha](https://github.com/jon7119/storcube_Ha).

---

## Contribution

Les tickets et pull requests sont les bienvenus.

Pour un problème de connexion ou de données manquantes, joignez les journaux en
`debug` — en particulier les lignes `Trame WebSocket sans batterie`, qui
documentent les formats d'API non encore gérés, ainsi que votre modèle de
batterie et votre version de firmware.

---

## Crédits

Basé sur le travail original de
[@jon7119](https://github.com/jon7119/storcube_Ha), sans lequel le protocole
n'aurait pas pu être rétro-ingénié.

## Licence

Voir le fichier [`LICENSE`](LICENSE).
