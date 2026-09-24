# Discord Bot Manager

Un custom component Home Assistant pour gérer un ou plusieurs bots Discord persistants, exposant vos automatisations et entités en commandes slash Discord.

[![Discord](https://img.shields.io/discord/732296796488822815?color=%235865F2&label=Discord&logo=discord&logoColor=white)](https://discord.gg/NzdCbuT3)
[![HACS Default](https://img.shields.io/badge/HACS-Default-blue.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/tag/pyriec/homeassistant-discord-bot-manager?label=version)](https://github.com/pyriec/homeassistant-discord-bot-manager)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Fonctionnalités

- **Connexion WebSocket Discord** : Le bot se connecte en arrière-plan sans bloquer Home Assistant
- **Commandes Slash dynamiques** : Récupère automatiquement les automatisations associées à des labels HA
- **Entités et templates Jinja2** : Configurez des commandes pour lire l'état d'entités avec rendu template personnalisé
- **Support YAML et UI** : Configuration via `configuration.yaml` ou interface utilisateur (config flow)
- **Synchronisation guild** : Option `guild_id` pour synchroniser instantanément les commandes sur un serveur Discord

## Installation

### Via HACS (recommandé)

1. Dans HACS, cliquez sur les trois points ⋮ en haut à droite → **Repositories personnalisés**
2. Collez l'URL suivante et cliquez sur **Ajouter** :
   ```
   https://github.com/pyriec/homeassistant-discord-bot-manager
   ```
3. Recherchez **Discord Bot Manager** dans HACS et cliquez sur **Installer**
4. Redémarrez Home Assistant

Ou utilisez le bouton ci-dessous pour ouvrir ce dépôt directement dans HACS depuis votre instance Home Assistant :

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=pyriec&repository=homeassistant-discord-bot-manager&category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open this repository in HACS">
  </a>
</p>

### Manuellement

1. Clonez ou téléchargez le dépôt
2. Copiez le dossier `custom_components/discord_bot_manager` dans votre répertoire `custom_components/` de Home Assistant
3. Redémarrez Home Assistant

## Configuration

### Via l'interface utilisateur (config flow)

1. Allez dans **Paramètres** → **Appareils et services**
2. Cliquez sur **Ajouter une intégration**
3. Recherchez **Discord Bot Manager**
4. Saisissez :
   - **Token** : votre token bot Discord (à récupérer sur [Discord Developer Portal](https://discord.com/developers/applications))
   - **Guild ID** (optionnel) : ID du serveur Discord pour synchronisation instantanée des commandes
   - **Labels** : étiquettes HA séparées par des virgules, associées aux automatisations à exposer

### Via YAML

Ajoutez à votre `configuration.yaml` :

```yaml
discord_bot_manager:
  bots:
    - token: !secret discord_token
      guild_id: "123456789012345678"  # Optionnel : sync instantanée sur ce serveur
      labels:
        - "discord_acces"
      entities:
        - entity_id: sensor.temperature_salon
          command: "temperature"
          description: "Affiche la température du salon"
          format: "🌡️ Il fait actuellement **{{ states('sensor.temperature_salon') }}°C** dans le salon."
        - entity_id: binary_sensor.porte_entree
          command: "porte"
          description: "État de la porte d'entrée"
          format: "🚪 La porte est {{ 'ouverte' if is_state('binary_sensor.porte_entree', 'on') else 'fermée' }}."
```

## Commandes Slash

### Commandes d'automatisation

Les automatisations HA portant les labels configurés sont automatiquement exposées comme commandes slash :

```
/trigger_entrée        → Déclenche l'automatisation "Entrée"
/trigger_arret_alarme  → Déclenche l'automatisation "Arrêt alarme"
```

### Commandes d'entités

Chaque entité configurée devient une commande slash avec rendu template Jinja2 :

```
/temperature
→ 🌡️ Il fait actuellement **22°C** dans le salon.

/porte
→ 🚪 La porte est fermée.
```

Variables disponibles dans le template :

| Variable | Description |
|---|---|
| `{{ state }}` | Valeur brute de l'entité |
| `{{ attributes }}` | Dictionnaire des attributs |
| `{{ entity_id }}` | ID complet de l'entité |
| `{{ entity }}` | L'objet `State` complet |

## Secrets

Créez un fichier `secrets.yaml` dans le répertoire de configuration :

```yaml
discord_token: "DISCORD_BOT_TOKEN_HERE"
```

## Services

| Service | Description |
|---|---|
| `discord_bot_manager.refresh_commands` | Re-synchronise l'arbre de commandes Discord (sync guild immédiate) |
| `discord_bot_manager.reconnect` | Recharge l'intégration (déconnecte puis reconnecte le bot) |

Exemple d'appel :

```yaml
service: discord_bot_manager.refresh_commands
data:
  entry_id: abcd1234efgh5678
```

## Développement

```bash
# Lancer les vérifications syntaxiques
python3 -m py_compile custom_components/discord_bot_manager/*.py
```

## License

MIT License — voir le fichier [LICENSE](LICENSE).

## Support

Pour le support, ouvrez une issue sur le [dépôt GitHub](https://github.com/pyriec/homeassistant-discord-bot-manager/issues).
