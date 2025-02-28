# Storcube Battery Monitor pour Home Assistant

Cette intégration personnalisée permet de surveiller l'état d'une batterie solaire Storcube via MQTT dans Home Assistant.

## Fonctionnalités

- Connexion MQTT automatique
- Surveillance en temps réel des données de la batterie :
  - Puissance solaire en entrée
  - Capacité restante de la batterie
  - Puissance délivrée par l'onduleur
  - État de la connexion MQTT
- Carte Lovelace personnalisée avec affichage graphique

## Installation

### Via HACS (recommandé)

1. Assurez-vous d'avoir [HACS](https://hacs.xyz/) installé
2. Ajoutez ce dépôt comme "Custom Repository" dans HACS
3. Recherchez "Storcube Battery Monitor" dans HACS et installez-le
4. Redémarrez Home Assistant

### Installation manuelle

1. Copiez le dossier `storcube_battery_monitor` dans le répertoire `custom_components` de votre installation Home Assistant
2. Redémarrez Home Assistant

## Configuration

1. Allez dans Configuration > Intégrations
2. Cliquez sur le bouton "+" pour ajouter une nouvelle intégration
3. Recherchez "Storcube Battery Monitor"
4. Remplissez les informations requises :
   - Adresse du broker MQTT
   - Port MQTT
   - Nom d'utilisateur MQTT
   - Mot de passe MQTT
   - ID de l'appareil
   - Code de l'application
   - Nom de connexion

## Utilisation de la carte Lovelace

Ajoutez la carte personnalisée à votre tableau de bord Lovelace :

```yaml
type: custom:storcube-battery-card
solar_power: sensor.storcube_solar_power
battery_capacity: sensor.storcube_battery_capacity
inverter_power: sensor.storcube_inverter_power
connection_status: binary_sensor.storcube_connection
```

## Entités disponibles

- `sensor.storcube_solar_power` : Puissance solaire en entrée (W)
- `sensor.storcube_battery_capacity` : Capacité restante de la batterie (Wh)
- `sensor.storcube_inverter_power` : Puissance délivrée par l'onduleur (W)
- `binary_sensor.storcube_connection` : État de la connexion MQTT

## Dépannage

1. Vérifiez que le broker MQTT est accessible
2. Vérifiez les logs de Home Assistant pour les messages d'erreur
3. Assurez-vous que les identifiants sont corrects

## Support

Pour obtenir de l'aide ou signaler un problème :
- Ouvrez une issue sur GitHub
- Consultez la documentation complète

## Licence

Ce projet est sous licence MIT. Voir le fichier LICENSE pour plus de détails. 