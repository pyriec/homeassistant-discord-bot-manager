# Discord Bot Manager

Un custom component Home Assistant pour gérer un ou plusieurs bots Discord persistants, exposant vos commandes en commandes slash Discord. Configuration simplifiée : seulement l'ID du serveur et le token du bot sont requis.

[![Discord](https://img.shields.io/discord/732296796488822815?color=%235865F2&label=Discord&logo=discord&logoColor=white)](https://discord.gg/NzdCbuT3)
[![HACS Default](https://img.shields.io/badge/HACS-Default-blue.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/tag/pyriec/homeassistant-discord-bot-manager?label=version)](https://github.com/pyriec/homeassistant-discord-bot-manager)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Fonctionnalités

- **Configuration simplifiée** : Seulement l'ID du serveur Discord et le token du bot sont requis
- **Commandes Slash dynamiques** : Créez, modifiez et supprimez des commandes depuis le panneau Lovelace
- **Gestion des étiquettes HA** : Créez et gérez les étiquettes Home Assistant directement
- **Template Jinja2** : Personnalisez le rendu des réponses avec des templates
- **Interface Lovelace complète** : Visualisez tous vos bots et leurs configurations
- **Support multi-bots** : Gérez plusieurs bots Discord simultanément

## Installation

### Via HACS (recommandé)

1. Dans HACS, cliquez sur les trois points ⋮ en haut à droite → **Repositories personnalisés**
2. Collez l'URL suivante et cliquez sur **Ajouter** :
   ```
   https://github.com/pyriec/homeassistant-discord-bot-manager
   ```
3. Recherchez **Discord Bot Manager** dans HACS et cliquez sur **Installer**
4. Redémarrez Home Assistant

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
   - **Nom du bot** (optionnel) : nom affiché dans HA
   - **Token** : votre token bot Discord (à récupérer sur [Discord Developer Portal](https://discord.com/developers/applications))
   - **Guild ID** (optionnel) : ID du serveur Discord pour synchronisation instantanée des commandes

### Via YAML

```yaml
discord_bot_manager:
  bots:
    - token: !secret discord_token
      guild_id: "123456789012345678"
```

## Panneau Lovelace

Ajoutez le card custom à votre dashboard :

```yaml
type: custom:discord-bot-manager-card
title: Discord Bot Manager
```

Le panneau affiche :
- **Liste des bots** configurés avec leur statut (online/offline/connecting)
- **Statistiques** : nombre de commandes, étiquettes
- **Gestion des commandes** :
  - ➕ Ajouter une nouvelle commande
  - ✏️ Modifier une commande existante (description, format)
  - 🗑️ Supprimer une commande
  - 🔄 Synchroniser les commandes avec Discord
- **Gestion des étiquettes** :
  - 🏷️ Ajouter une étiquette
  - Supprimer une étiquette

## Commandes Slash

Les commandes créées via le panneau Lovelace deviennent des commandes slash Discord :

```
/commande    → Réponse avec le template défini
```

Variables disponibles dans le template Jinja2 :

| Variable | Description |
|----------|-------------|
| `{{ state }}` | Valeur brute de l'entité |
| `{{ attributes }}` | Dictionnaire des attributs |
| `{{ entity_id }}` | ID complet de l'entité |
| `{{ entity }}` | L'objet `State` complet |

## Services

| Service | Description |
|---------|-------------|
| `discord_bot_manager.get_config` | Retourne la configuration complète d'un bot |
| `discord_bot_manager.add_command` | Ajoute une nouvelle commande |
| `discord_bot_manager.update_command` | Modifie une commande existante |
| `discord_bot_manager.remove_command` | Supprime une commande |
| `discord_bot_manager.add_label` | Ajoute une étiquette au bot |
| `discord_bot_manager.remove_label` | Supprime une étiquette du bot |
| `discord_bot_manager.create_label` | Crée une nouvelle étiquette HA |
| `discord_bot_manager.refresh_commands` | Resynchronise l'arbre de commandes Discord |
| `discord_bot_manager.reconnect` | Recharge l'intégration (déconnecte puis reconnecte) |

Exemple d'appel :
```yaml
service: discord_bot_manager.add_command
data:
  entry_id: abc123
  command: temperature
  description: "Affiche la température"
  format: "🌡️ Il fait {{ states('sensor.temperature') }}°C"
```

## Secrets

Optionnel pour configuration YAML :
```yaml
# secrets.yaml
discord_token: "DISCORD_BOT_TOKEN_HERE"
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
