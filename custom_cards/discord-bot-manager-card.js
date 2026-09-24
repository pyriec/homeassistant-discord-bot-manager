/**
 * Discord Bot Manager Custom Lovelace Card
 * 
 * Affiche et gère tous les bots Discord configurés.
 * Permet de: voir les commandes, modifier descriptions, ajouter/supprimer commandes,
 * gérer les étiquettes HA, et synchroniser les commandes.
 */

(function() {
    'use strict';

    class DiscordBotManagerCard extends HTMLElement {
        constructor() {
            super();
            this._hass = null;
            this._config = null;
            this._bots = [];
            this._selectedBot = null;
            this._editingCommand = null;
        }

        setConfig(config) {
            this._config = config;
        }

        async connectedCallback() {
            this.render();
        }

        disconnectedCallback() {
            // Cleanup if needed
        }

        static getStubConfig() {
            return {
                title: 'Discord Bot Manager',
                view_title: 'Discord'
            };
        }

        getCardSize() {
            return 3;
        }

        setHass(hass) {
            this._hass = hass;
            this._loadBots();
            this.render();
        }

        async _loadBots() {
            try {
                const response = await this._hass.callService(
                    'discord_bot_manager',
                    'get_config'
                );
                this._bots = response.result || [];
                if (this._bots.length > 0 && !this._selectedBot) {
                    this._selectedBot = this._bots[0].entry_id;
                }
            } catch (error) {
                console.error('Failed to load bots:', error);
            }
        }

        _maskToken(token) {
            if (!token || token.length <= 10) return '****...';
            return token.slice(0, 10) + '...';
        }

        _getStatusIcon(status) {
            switch(status) {
                case 'online': return 'mdi:discord';
                case 'offline': return 'mdi:discord-horizontal';
                case 'connecting': return 'mdi:discord';
                default: return 'mdi:discord';
            }
        }

        _getStatusColor(status) {
            switch(status) {
                case 'online': return '#5865F2';
                case 'offline': return '#747F8D';
                case 'connecting': return '#F0CD4C';
                default: return '#747F8D';
            }
        }

        _addCommand() {
            const command = prompt('Nom de la nouvelle commande:');
            if (!command) return;
            
            const description = prompt('Description (optionnel):', '') || '';
            const format = prompt('Format Jinja2 (optionnel):', '{{ states(entity_id) }}') || '{{ states(entity_id) }}';
            const entityId = prompt('ID de l\'entité HA (optionnel):', '') || '';

            this._hass.callService('discord_bot_manager', 'add_command', {
                entry_id: this._selectedBot,
                command: command,
                description: description,
                format: format,
                entity_id: entityId
            }).then(() => {
                this._loadBots();
            });
        }

        _removeCommand(commandName) {
            if (!confirm(`Supprimer la commande "${commandName}" ?`)) return;

            this._hass.callService('discord_bot_manager', 'remove_command', {
                entry_id: this._selectedBot,
                command: commandName
            }).then(() => {
                this._loadBots();
            });
        }

        _editCommand(command) {
            const newDesc = prompt('Nouvelle description:', command.description || '');
            if (newDesc === null) return;

            const newFormat = prompt('Nouveau format Jinja2:', command.format || '{{ states(entity_id) }}');
            if (newFormat === null) return;

            this._hass.callService('discord_bot_manager', 'update_command', {
                entry_id: this._selectedBot,
                command: command.command,
                description: newDesc,
                format: newFormat,
                entity_id: command.entity_id
            }).then(() => {
                this._loadBots();
            });
        }

        _addLabel() {
            const label = prompt('Nom de la nouvelle étiquette:');
            if (!label) return;

            this._hass.callService('discord_bot_manager', 'create_label', {
                label: label
            }).then(() => {
                this._hass.callService('discord_bot_manager', 'add_label', {
                    entry_id: this._selectedBot,
                    label: label
                }).then(() => {
                    this._loadBots();
                });
            });
        }

        _removeLabel(label) {
            if (!confirm(`Supprimer l'étiquette "${label}" ?`)) return;

            this._hass.callService('discord_bot_manager', 'remove_label', {
                entry_id: this._selectedBot,
                label: label
            }).then(() => {
                this._loadBots();
            });
        }

        _refreshCommands() {
            this._hass.callService('discord_bot_manager', 'refresh_commands', {
                entry_id: this._selectedBot
            }).then(() => {
                this._loadBots();
            });
        }

        _reconnect() {
            if (!confirm('Reconnecter le bot ?')) return;

            this._hass.callService('discord_bot_manager', 'reconnect', {
                entry_id: this._selectedBot
            }).then(() => {
                this._loadBows();
            });
        }

        _selectBot(entryId) {
            this._selectedBot = entryId;
            this.render();
        }

        render() {
            if (!this._hass) return;

            const currentBot = this._bots.find(b => b.entry_id === this._selectedBot);
            const bots = this._bots || [];

            let html = `
                <style>
                    :host {
                        display: block;
                        font-family: 'Inter', -apple-system, sans-serif;
                    }
                    .card {
                        background: var(--card-background-color, var(--ha-card-background, #fff));
                        border-radius: var(--ha-card-border-radius, 12px);
                        padding: 16px;
                        box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,0.08));
                        border: 1px solid var(--divider-color, #e0e0e0);
                    }
                    .header {
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                        margin-bottom: 16px;
                    }
                    .header h2 {
                        margin: 0;
                        font-size: 18px;
                        font-weight: 600;
                        color: var(--primary-text-color, #000);
                    }
                    .bot-list {
                        margin-bottom: 20px;
                    }
                    .bot-item {
                        display: flex;
                        align-items: center;
                        padding: 12px;
                        margin-bottom: 8px;
                        border-radius: 8px;
                        cursor: pointer;
                        transition: background 0.2s;
                        border: 1px solid var(--divider-color, #e0e0e0);
                    }
                    .bot-item:hover {
                        background: var(--hover-background, #f5f5f5);
                    }
                    .bot-item.selected {
                        background: var(--primary-color, #03a9f4);
                        color: white;
                        border-color: var(--primary-color, #03a9f4);
                    }
                    .bot-item.selected .bot-status,
                    .bot-item.selected .bot-name {
                        color: white;
                    }
                    .bot-icon {
                        font-size: 24px;
                        margin-right: 12px;
                    }
                    .bot-info {
                        flex: 1;
                    }
                    .bot-name {
                        font-weight: 500;
                        font-size: 14px;
                    }
                    .bot-meta {
                        font-size: 12px;
                        opacity: 0.7;
                        margin-top: 2px;
                    }
                    .bot-status {
                        font-size: 12px;
                        font-weight: 500;
                    }
                    .section {
                        margin-top: 20px;
                    }
                    .section-title {
                        font-size: 14px;
                        font-weight: 600;
                        color: var(--secondary-text-color, #666);
                        margin-bottom: 12px;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                    }
                    .command-list {
                        max-height: 300px;
                        overflow-y: auto;
                    }
                    .command-item {
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                        padding: 10px 12px;
                        margin-bottom: 6px;
                        background: var(--secondary-background-color, #f5f5f5);
                        border-radius: 6px;
                        font-size: 13px;
                    }
                    .command-info {
                        flex: 1;
                    }
                    .command-name {
                        font-weight: 500;
                        color: var(--primary-text-color, #000);
                    }
                    .command-desc {
                        font-size: 12px;
                        color: var(--secondary-text-color, #666);
                        margin-top: 2px;
                    }
                    .command-actions {
                        display: flex;
                        gap: 8px;
                    }
                    .btn {
                        padding: 6px 12px;
                        border: none;
                        border-radius: 6px;
                        font-size: 12px;
                        font-weight: 500;
                        cursor: pointer;
                        transition: all 0.2s;
                    }
                    .btn-primary {
                        background: var(--primary-color, #03a9f4);
                        color: white;
                    }
                    .btn-primary:hover {
                        background: var(--primary-color-dark, #0288d1);
                    }
                    .btn-secondary {
                        background: var(--secondary-background-color, #e0e0e0);
                        color: var(--primary-text-color, #000);
                    }
                    .btn-secondary:hover {
                        background: var(--divider-color, #ccc);
                    }
                    .btn-danger {
                        background: #f44336;
                        color: white;
                    }
                    .btn-danger:hover {
                        background: #d32f2f;
                    }
                    .btn-success {
                        background: #4caf50;
                        color: white;
                    }
                    .btn-success:hover {
                        background: #388e3c;
                    }
                    .actions-bar {
                        display: flex;
                        gap: 8px;
                        margin-bottom: 16px;
                        flex-wrap: wrap;
                    }
                    .empty-state {
                        text-align: center;
                        padding: 40px 20px;
                        color: var(--secondary-text-color, #666);
                    }
                    .empty-state svg {
                        width: 64px;
                        height: 64px;
                        margin-bottom: 16px;
                        opacity: 0.3;
                    }
                    .label-tag {
                        display: inline-flex;
                        align-items: center;
                        padding: 4px 10px;
                        background: var(--secondary-background-color, #f0f0f0);
                        border-radius: 12px;
                        font-size: 12px;
                        margin-right: 6px;
                        margin-bottom: 6px;
                    }
                    .label-tag .remove {
                        margin-left: 6px;
                        cursor: pointer;
                        opacity: 0.6;
                    }
                    .label-tag .remove:hover {
                        opacity: 1;
                    }
                    .stats {
                        display: flex;
                        gap: 16px;
                        margin-bottom: 16px;
                        flex-wrap: wrap;
                    }
                    .stat-item {
                        background: var(--secondary-background-color, #f5f5f5);
                        padding: 12px 16px;
                        border-radius: 8px;
                        flex: 1;
                        min-width: 120px;
                    }
                    .stat-value {
                        font-size: 24px;
                        font-weight: 600;
                        color: var(--primary-color, #03a9f4);
                    }
                    .stat-label {
                        font-size: 12px;
                        color: var(--secondary-text-color, #666);
                        margin-top: 4px;
                    }
                </style>
                <div class="card">
                    <div class="header">
                        <h2>🤖 Discord Bot Manager</h2>
                    </div>
                    
                    ${bots.length === 0 ? `
                        <div class="empty-state">
                            <svg viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
                            </svg>
                            <p>Aucun bot configuré</p>
                            <p style="font-size: 12px;">Ajoutez un bot via Paramètres → Appareils et services</p>
                        </div>
                    ` : `
                        <div class="bot-list">
                            ${bots.map(bot => `
                                <div class="bot-item ${bot.entry_id === this._selectedBot ? 'selected' : ''}" 
                                     onclick="this.getRootNode().host._selectBot('${bot.entry_id}')">
                                    <span class="bot-icon" style="color: ${this._getStatusColor(bot.status)}">
                                        ${this._getStatusIcon(bot.status)}
                                    </span>
                                    <div class="bot-info">
                                        <div class="bot-name">${bot.bot_name || 'Discord Bot'}</div>
                                        <div class="bot-meta">
                                            ${bot.guild_id ? `Server: ${bot.guild_id} • ` : ''}
                                            ${bot.total_commands} commandes • Token: ${this._maskToken(bot.token_masked)}
                                        </div>
                                    </div>
                                    <span class="bot-status">${bot.status}</span>
                                </div>
                            `).join('')}
                        </div>
                    `}

                    ${currentBot ? `
                        <div class="stats">
                            <div class="stat-item">
                                <div class="stat-value">${currentBot.total_commands}</div>
                                <div class="stat-label">Commandes</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value">${currentBot.labels ? currentBot.labels.length : 0}</div>
                                <div class="stat-label">Étiquettes</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value">${currentBot.status}</div>
                                <div class="stat-label">Statut</div>
                            </div>
                        </div>

                        <div class="actions-bar">
                            <button class="btn btn-success" onclick="this.getRootNode().host._addCommand()">
                                ➕ Ajouter une commande
                            </button>
                            <button class="btn btn-primary" onclick="this.getRootNode().host._addLabel()">
                                🏷️ Ajouter une étiquette
                            </button>
                            <button class="btn btn-secondary" onclick="this.getRootNode().host._refreshCommands()">
                                🔄 Synchroniser
                            </button>
                            <button class="btn btn-secondary" onclick="this.getRootNode().host._reconnect()">
                                🔌 Reconnecter
                            </button>
                        </div>

                        <div class="section">
                            <div class="section-title">Commandes</div>
                            <div class="command-list">
                                ${(currentBot.commands || []).map(cmd => `
                                    <div class="command-item">
                                        <div class="command-info">
                                            <div class="command-name">/${cmd.command}</div>
                                            <div class="command-desc">${cmd.description || 'Aucune description'}</div>
                                            ${cmd.entity_id ? `<div class="command-desc">Entité: ${cmd.entity_id}</div>` : ''}
                                        </div>
                                        <div class="command-actions">
                                            <button class="btn btn-secondary" onclick="this.getRootNode().host._editCommand(${JSON.stringify(cmd).replace(/"/g, '&quot;')})">
                                                ✏️
                                            </button>
                                            <button class="btn btn-danger" onclick="this.getRootNode().host._removeCommand('${cmd.command}')">
                                                🗑️
                                            </button>
                                        </div>
                                    </div>
                                `).join('')}
                                ${(currentBot.commands || []).length === 0 ? `
                                    <div class="empty-state" style="padding: 20px;">
                                        <p>Aucune commande configurée</p>
                                    </div>
                                ` : ''}
                            </div>
                        </div>

                        <div class="section">
                            <div class="section-title">Étiquettes</div>
                            <div>
                                ${(currentBot.labels || []).map(label => `
                                    <span class="label-tag">
                                        ${label}
                                        <span class="remove" onclick="this.getRootNode().host._removeLabel('${label}')">×</span>
                                    </span>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;

            this.innerHTML = html;
        }

        getDisplayInfo() {
            return `${this._bots.length} bot(s)`;
        }
    }

    customElements.define('discord-bot-manager-card', DiscordBotManagerCard);
    
    window.customCards = window.customCards || [];
    window.customCards.push({
        type: 'discord-bot-manager-card',
        name: 'Discord Bot Manager',
        preview: true,
        description: 'Gérez vos bots Discord et leurs commandes depuis le panneau Lovelace'
    });
})();
