Client de la batterie MQTT

Script local pour récupérer Data pour ASGOFT ASE 1000 et les variantes connexes de la batterie solaire Storcube .

Créer une image docker en utilisant

docker build -t battery-mqtt-client .

Exécuter en utilisant:

docker run -d \
  -e MQTT_BROKER='192.168.1.2' \
  -e MQTT_PORT='1883' \
  -e DEVICE_ID='DEVICE ID FROM APP'
  -e APP_CODE='Storcube' \
  -e LOGIN_NAME='test@example.com' \
  -e PASSWORD='YourPassword' \
  -e MQTT_PASSWORD='test' \
  -e MQTT_USERNAME='test' \
  --name battery-mqtt-client battery-mqtt-client

Sinon, modifier la section de configuration et exécuter le script directement
Paramètres de configuration

Cette application peut être configurée par les variables d'environnement suivantes. Veuillez noter que certains d'entre eux sont obligatoires pour que l'application fonctionne correctement:

    MQTT_BROKER(obligatoire):
        Description : L'adresse IP ou le nom d'hôte du courtier MQTT.
        Par défaut : Néant (doit être fourni).

    MQTT_PORT(facultatif):
        Description : Le numéro de port sur lequel le courtier MQTT écoute.
        Par défaut : 1883.

    MQTT_TOPIC(facultatif):
        Description : Le thème MQTT où les messages seront publiés.
        Par défaut : battery/reportEquip.

    WS_URI(facultatif):
        Description : L'URI complet pour établir la connexion WebSocket.
        Par défaut : ws://baterway.com:9501/equip/info/.

    TOKEN_URL(obligatoire):
        Description : L'URL pour récupérer le jeton d'autorisation requis pour l'authentification WebSocket.
        Par défaut : http://baterway.com/api/user/app/login.

    HEARTBEAT_INTERVAL(facultatif):
        Description : L'intervalle en secondes entre chaque message de battement cardiaque envoyé pour maintenir la connexion WebSocket.
        Par défaut : 60secondes.

    RECONNECT_DELAY(facultatif):
        Description : Le retard en quelques secondes avant de tenter de se reconnecter après une perte de connexion.
        Par défaut : 60secondes.

    APP_CODE(obligatoire):
        Description : Le code de demande utilisé dans le cadre du processus d'authentification pour aller chercher le jeton. Batterie ASGOFT ou Storcube)
        Par défaut : ASGOFT.

    LOGIN_NAME(obligatoire):
        Description : Le nom de connexion utilisé en conjonction avec PASSWORDà des fins d'authentification.
        Par défaut : Néant (doit être fourni).

    PASSWORD(obligatoire):
        Description : Le mot de passe correspondant à la LOGIN_NAMEà des fins d'authentification.
        Par défaut : Néant (doit être fourni).

    DEVICE_ID(obligatoire):
        Description : L'ID du dispositif à récupérer. Est affiché dans l'application A-Solar.
        Par défaut : Néant (doit être fourni).
