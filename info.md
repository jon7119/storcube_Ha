# Storcube Battery Monitor

## Installation via HACS

1. **Prérequis** :
   - [HACS](https://hacs.xyz/) doit être installé dans votre Home Assistant
   - Un broker MQTT configuré et fonctionnel
   - Vos identifiants Baterway (Login et Password)
   - Le Device ID de votre batterie Storcube

2. **Ajout du dépôt** :
   - Dans Home Assistant, ouvrez HACS
   - Allez dans l'onglet "Intégrations"
   - Cliquez sur le menu (3 points) en haut à droite
   - Sélectionnez "Dépôts personnalisés"
   - Collez l'URL : `https://github.com/jon7119/storcube_Ha`
   - Choisissez la catégorie : "Integration"
   - Cliquez sur "Ajouter"

3. **Installation** :
   - Rafraîchissez la page HACS si nécessaire
   - Recherchez "Storcube Battery Monitor"
   - Cliquez sur "Télécharger"
   - Redémarrez Home Assistant

4. **Configuration** :
   - Allez dans Configuration > Intégrations
   - Cliquez sur "Ajouter une intégration"
   - Recherchez "Storcube Battery Monitor"
   - Remplissez les informations :
     - Broker MQTT (ex: 192.168.1.xxx)
     - Port MQTT (défaut: 1883)
     - Device ID (sur l'étiquette de votre batterie)
     - App Code (défaut: Storcube)
     - Login Baterway
     - Password Baterway
     - Identifiants MQTT

## Capteurs disponibles

- Niveau de batterie (%)
- Puissance actuelle (W)
- Seuil de batterie (%)
- État de la batterie
- Version du firmware

## Support

- [Documentation](https://github.com/jon7119/storcube_Ha)
- [Signaler un problème](https://github.com/jon7119/storcube_Ha/issues) 