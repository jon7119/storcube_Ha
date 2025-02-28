# StorCube Battery Monitor pour Home Assistant

Cette intégration personnalisée permet de surveiller l'état d'une batterie solaire Storcube via MQTT dans Home Assistant.

## Caractéristiques

- Connexion MQTT automatique
- Surveillance en temps réel des données de la batterie :
  - Puissance solaire en entrée
  - Capacité restante de la batterie
  - Puissance délivrée par l'onduleur
  - État de la connexion MQTT
- Carte Lovelace personnalisée avec affichage graphique

## Configuration

1. Allez dans Configuration > Intégrations
2. Cliquez sur le bouton "+" pour ajouter une nouvelle intégration
3. Recherchez "Storcube Battery Monitor"
4. Remplissez les informations requises :
   - Adresse du broker MQTT
   - Port MQTT
   - Nom d'utilisateur MQTT
   - Mot de passe MQTT
   - Code de l'application
   - Nom de connexion
   - Mot de passe de l'appareil 