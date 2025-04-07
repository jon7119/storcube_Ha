![](/custom_components/storcube_ha/res/logo.png)

# Storcube Battery Monitor pour Home Assistant

Cette intégration permet de connecter votre batterie Storcube à Home Assistant via MQTT (fonctionne sans). Elle récupère les données de la batterie depuis le serveur Baterway et les transmet à Home Assistant.

## Fonctionnalités

- Récupération des données de la batterie en temps réel via WebSocket
- Transmission des données via MQTT (fonctionne sans)
- Configuration via l'interface utilisateur de Home Assistant
- Gestion automatique des reconnexions
- Capteurs disponibles :
  - Niveau de batterie (%)
  - Puissance (W)
  - Seuil de batterie (%) (en cours)
  - État de la batterie
  - Version du firmware (en cours)

## Prérequis

- Home Assistant
- Un broker MQTT configuré et fonctionnel
- Les informations de connexion à votre batterie Storcube :
  - Device ID (identifiant de votre batterie)
  - App Code (par défaut : Storcube)
  - Login Name (votre identifiant Baterway)
  - Password (votre mot de passe Baterway)

## Installation

### Option 1 : Via HACS (recommandé)

1. **Installation de HACS** (si pas déjà fait) :
   - Suivez le [guide d'installation de HACS](https://hacs.xyz/docs/setup/download)
   - Redémarrez Home Assistant après l'installation

2. **Ajout du dépôt personnalisé** :
   - Ouvrez HACS dans Home Assistant
   - Allez dans l'onglet "Intégrations"
   - Cliquez sur le menu (3 points) en haut à droite
   - Sélectionnez "Dépôts personnalisés"
   - Collez l'URL : `https://github.com/jon7119/storcube_Ha`
   - Sélectionnez la catégorie : "Integration"
   - Cliquez sur "Ajouter"

3. **Installation de l'intégration** :
   - Rafraîchissez la page HACS si nécessaire
   - Recherchez "Storcube Battery Monitor"
   - Cliquez sur "Télécharger"
   - Redémarrez Home Assistant

### Option 2 : Installation manuelle

1. Téléchargez la dernière version depuis [GitHub](https://github.com/jon7119/storcube_Ha)
2. Décompressez l'archive
3. Copiez le dossier `custom_components/storcube_ha` dans le dossier `custom_components` de votre installation Home Assistant
4. Redémarrez Home Assistant

## Configuration

Après l'installation (via HACS ou manuellement) :

1. Dans Home Assistant, allez dans Configuration > Intégrations
2. Cliquez sur le bouton "+" pour ajouter une nouvelle intégration
3. Recherchez "Storcube Battery Monitor"
4. Remplissez les informations requises :(si pas de mqtt mettre test (fonctionne sans)
   - Adresse du broker MQTT (ex: 192.168.1.xxx)
   - Port MQTT (par défaut : 1883)
   - Device ID (sur l'étiquette de votre batterie)
   - App Code (par défaut : Storcube)
   - Login Name (votre identifiant Baterway)
   - Password (votre mot de passe Baterway)
   - Nom d'utilisateur MQTT
   - Mot de passe MQTT

## Dépannage

### Les données ne sont pas mises à jour

1. Vérifiez que votre broker MQTT est accessible
2. Vérifiez les logs de Home Assistant pour plus d'informations
3. Assurez-vous que vos identifiants Baterway sont corrects
4. Vérifiez que votre Device ID correspond bien à celui de votre batterie

### Erreurs de connexion

1. Vérifiez votre connexion Internet
2. Vérifiez que le serveur Baterway est accessible
3. Vérifiez vos identifiants dans la configuration

## Support

Si vous rencontrez des problèmes ou avez des questions :

1. Consultez la [documentation](https://github.com/jon7119/storcube_Ha)
2. Ouvrez une [issue sur GitHub](https://github.com/jon7119/storcube_Ha/issues)

## Licence

Ce projet est sous licence MIT. Voir le fichier LICENSE pour plus de détails.

## Badges

[![CodeQL](https://github.com/jon7119/storcube_Ha/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/jon7119/storcube_Ha/actions/workflows/github-code-scanning/codeql)
[![HACS](https://github.com/jon7119/storcube_Ha/actions/workflows/hacs.yaml/badge.svg)](https://github.com/jon7119/storcube_Ha/actions/workflows/hacs.yaml)
[![hassfest](https://github.com/jon7119/storcube_Ha/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/jon7119/storcube_Ha/actions/workflows/hassfest.yaml)
[![Validate](https://github.com/jon7119/storcube_Ha/actions/workflows/validate.yml/badge.svg)](https://github.com/jon7119/storcube_Ha/actions/workflows/validate.yml)

