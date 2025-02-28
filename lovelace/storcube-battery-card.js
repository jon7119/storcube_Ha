class StorcubeBatteryCard extends HTMLElement {
    set hass(hass) {
        if (!this.content) {
            this.innerHTML = `
                <ha-card>
                    <div class="card-content">
                        <div class="battery-container">
                            <div class="battery-info">
                                <div class="battery-level">
                                    <div class="battery-icon"></div>
                                    <div class="battery-percentage"></div>
                                </div>
                                <div class="power-flow">
                                    <div class="solar-power">
                                        <ha-icon icon="mdi:solar-power"></ha-icon>
                                        <span class="value"></span>
                                    </div>
                                    <div class="battery-power">
                                        <ha-icon icon="mdi:battery"></ha-icon>
                                        <span class="value"></span>
                                    </div>
                                    <div class="inverter-power">
                                        <ha-icon icon="mdi:power-plug"></ha-icon>
                                        <span class="value"></span>
                                    </div>
                                </div>
                            </div>
                            <div class="connection-status">
                                <ha-icon icon="mdi:wifi"></ha-icon>
                            </div>
                        </div>
                    </div>
                </ha-card>
            `;
            this.content = this.querySelector('.card-content');
            
            const style = document.createElement('style');
            style.textContent = `
                .battery-container {
                    padding: 16px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                }
                .battery-info {
                    width: 100%;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 16px;
                }
                .battery-level {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .battery-icon {
                    width: 40px;
                    height: 80px;
                    border: 2px solid var(--primary-text-color);
                    border-radius: 4px;
                    position: relative;
                }
                .battery-icon::before {
                    content: '';
                    position: absolute;
                    bottom: 0;
                    left: 0;
                    width: 100%;
                    background: var(--primary-color);
                    transition: height 0.3s ease;
                }
                .battery-percentage {
                    font-size: 24px;
                    font-weight: bold;
                }
                .power-flow {
                    width: 100%;
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 16px;
                    text-align: center;
                }
                .power-flow > div {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 4px;
                }
                .connection-status {
                    margin-top: 16px;
                }
                .connection-status ha-icon {
                    color: var(--success-color);
                }
                .connection-status.disconnected ha-icon {
                    color: var(--error-color);
                }
            `;
            this.appendChild(style);
        }

        const solarPower = hass.states[this._config.solar_power];
        const batteryCapacity = hass.states[this._config.battery_capacity];
        const inverterPower = hass.states[this._config.inverter_power];
        const connectionStatus = hass.states[this._config.connection_status];

        if (solarPower && batteryCapacity && inverterPower && connectionStatus) {
            const batteryPercentage = (batteryCapacity.state / batteryCapacity.attributes.max) * 100;
            
            this.content.querySelector('.battery-icon').style.setProperty(
                '--battery-level',
                `${batteryPercentage}%`
            );
            this.content.querySelector('.battery-percentage').textContent = 
                `${Math.round(batteryPercentage)}%`;
            
            this.content.querySelector('.solar-power .value').textContent = 
                `${solarPower.state} ${solarPower.attributes.unit_of_measurement}`;
            
            this.content.querySelector('.battery-power .value').textContent = 
                `${batteryCapacity.state} ${batteryCapacity.attributes.unit_of_measurement}`;
            
            this.content.querySelector('.inverter-power .value').textContent = 
                `${inverterPower.state} ${inverterPower.attributes.unit_of_measurement}`;
            
            const connectionStatusEl = this.content.querySelector('.connection-status');
            connectionStatusEl.classList.toggle('disconnected', connectionStatus.state !== 'on');
        }
    }

    setConfig(config) {
        if (!config.solar_power || !config.battery_capacity || 
            !config.inverter_power || !config.connection_status) {
            throw new Error('Please define all required entities');
        }
        this._config = config;
    }

    getCardSize() {
        return 3;
    }

    static getConfigElement() {
        return document.createElement('storcube-battery-card-editor');
    }

    static getStubConfig() {
        return {
            solar_power: 'sensor.storcube_solar_power',
            battery_capacity: 'sensor.storcube_battery_capacity',
            inverter_power: 'sensor.storcube_inverter_power',
            connection_status: 'binary_sensor.storcube_connection'
        };
    }
}

customElements.define('storcube-battery-card', StorcubeBatteryCard); 