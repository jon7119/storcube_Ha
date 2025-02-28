# Storcube Battery Monitor pour Home Assistant

Cette intégration permet de connecter votre batterie Storcube à Home Assistant via MQTT. Elle récupère les données de la batterie depuis le serveur Baterway et les transmet à Home Assistant.

## Fonctionnalités

- Récupération des données de la batterie en temps réel via WebSocket
- Transmission des données via MQTT
- Configuration via l'interface utilisateur de Home Assistant
- Gestion automatique des reconnexions
- Capteurs disponibles :
  - Niveau de batterie (%)
  - Puissance (W)
  - Seuil de batterie (%)
  - État de la batterie
  - Version du firmware

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

1. Assurez-vous d'avoir [HACS](https://hacs.xyz/) installé
2. Allez dans HACS > Intégrations
3. Cliquez sur les 3 points en haut à droite et choisissez "Dépôts personnalisés"
4. Ajoutez `https://github.com/jon7119/storcube_Ha` comme dépôt personnalisé
5. Catégorie : Integration
6. Cliquez sur "Storcube Battery Monitor" dans la liste
7. Cliquez sur "Télécharger"
8. Redémarrez Home Assistant

### Option 2 : Installation manuelle

1. Téléchargez la dernière version depuis [GitHub](https://github.com/jon7119/storcube_Ha)
2. Copiez le dossier `custom_components/storcube_ha` dans votre dossier `custom_components` de Home Assistant
3. Redémarrez Home Assistant

## Configuration

Après l'installation :

1. Dans Home Assistant, allez dans Configuration > Intégrations
2. Cliquez sur le bouton "+" pour ajouter une nouvelle intégration
3. Recherchez "Storcube Battery Monitor"
4. Remplissez les informations requises :
   - Adresse du broker MQTT
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

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Validate with hassfest](https://github.com/jon7119/storcube_Ha/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/jon7119/storcube_Ha/actions/workflows/hassfest.yaml)
[![HACS Action](https://github.com/jon7119/storcube_Ha/actions/workflows/hacs.yaml/badge.svg)](https://github.com/jon7119/storcube_Ha/actions/workflows/hacs.yaml) 