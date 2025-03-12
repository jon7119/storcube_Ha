# Storcube Battery Monitor

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Cette intégration Home Assistant permet de surveiller et contrôler les batteries Storcube.

## Fonctionnalités

- Surveillance du niveau de batterie
- Surveillance de la puissance de charge/décharge
- Surveillance de la température
- Surveillance de la production solaire
- Contrôle de la puissance de sortie
- Compatible avec le dashboard Énergie de Home Assistant

## Installation

### Installation via HACS

1. Assurez-vous d'avoir [HACS](https://hacs.xyz/) installé
2. Allez dans HACS > Intégrations > Menu (trois points) > Dépôts personnalisés
3. Ajoutez l'URL du dépôt : `https://github.com/jon7119/storcube_Ha`
4. Cliquez sur "Ajouter"
5. Recherchez "Storcube Battery Monitor" dans les intégrations HACS
6. Cliquez sur "Télécharger"
7. Redémarrez Home Assistant

### Installation manuelle

1. Téléchargez le dossier `custom_components/storcube_ha`
2. Copiez-le dans votre dossier `custom_components`
3. Redémarrez Home Assistant

## Configuration

1. Allez dans Paramètres > Appareils et services > Ajouter une intégration
2. Recherchez "Storcube Battery Monitor"
3. Suivez les instructions pour configurer l'intégration

## Versions

### v1.0.0
- Version initiale
- Support des capteurs de base
- Support du dashboard Énergie

## Dépannage

Si vous rencontrez des problèmes, veuillez consulter les journaux de Home Assistant ou ouvrir un ticket sur GitHub.

## Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une pull request ou un ticket sur GitHub. 