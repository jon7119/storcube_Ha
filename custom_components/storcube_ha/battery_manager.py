"""Gestionnaire de batteries empilées pour StorCube."""
from __future__ import annotations

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

@dataclass
class BatteryInfo:
    """Informations d'une batterie individuelle."""
    equip_id: str
    soc: Optional[int] = None
    temp: Optional[float] = None
    capacity: Optional[float] = None
    pv1power: Optional[int] = None
    pv2power: Optional[int] = None
    invPower: Optional[int] = None
    isWork: Optional[int] = None
    is_master: bool = False
    last_update: Optional[datetime] = None

@dataclass
class StackInfo:
    """Informations de la pile de batteries."""
    main_equip_id: str
    total_capacity: Optional[float] = None
    total_pv1power: Optional[int] = None
    total_pv2power: Optional[int] = None
    total_inv_power: Optional[int] = None
    plug_power: Optional[int] = None
    last_update: Optional[datetime] = None

class StorCubeBatteryManager:
    """Gestionnaire pour les batteries StorCube empilées."""
    
    def __init__(self):
        """Initialiser le gestionnaire de batteries."""
        self.batteries: Dict[str, BatteryInfo] = {}
        self.stack_info: Optional[StackInfo] = None
        self.known_equip_ids: set = set()
        
    def update_from_output_api(self, output_data: Dict[str, Any]) -> None:
        """Mettre à jour les informations depuis l'API output."""
        try:
            if "equipIds" in output_data:
                equip_ids = output_data["equipIds"]
                if isinstance(equip_ids, list):
                    # Détecter de nouvelles batteries
                    for equip_id in equip_ids:
                        if equip_id not in self.known_equip_ids:
                            _LOGGER.info("Nouvelle batterie détectée: %s", equip_id)
                            self.batteries[equip_id] = BatteryInfo(equip_id=equip_id)
                            self.known_equip_ids.add(equip_id)
                    
                    # Marquer la batterie maître si elle est dans equipIds
                    main_equip_id = output_data.get("equipId")
                    if main_equip_id in self.batteries:
                        self.batteries[main_equip_id].is_master = True
                        _LOGGER.debug("Batterie maître identifiée: %s", main_equip_id)
                        
        except Exception as e:
            _LOGGER.error("Erreur lors de la mise à jour depuis l'API output: %s", e)
    
    def update_from_websocket(self, websocket_data: Dict[str, Any]) -> None:
        """Mettre à jour les informations depuis le WebSocket."""
        try:
            current_time = datetime.now()
            
            # Mettre à jour les informations de la pile
            if "mainEquipId" in websocket_data:
                main_equip_id = websocket_data["mainEquipId"]
                self.stack_info = StackInfo(
                    main_equip_id=main_equip_id,
                    total_capacity=websocket_data.get("totalCapacity"),
                    total_pv1power=websocket_data.get("totalPv1power"),
                    total_pv2power=websocket_data.get("totalPv2power"),
                    total_inv_power=websocket_data.get("totalInvPower"),
                    plug_power=websocket_data.get("plugPower"),
                    last_update=current_time
                )
                
                # Marquer la batterie maître
                if main_equip_id in self.batteries:
                    self.batteries[main_equip_id].is_master = True
            
            # Mettre à jour les informations individuelles des batteries
            if "list" in websocket_data and isinstance(websocket_data["list"], list):
                for battery_data in websocket_data["list"]:
                    equip_id = battery_data.get("equipId")
                    if equip_id:
                        # Créer la batterie si elle n'existe pas
                        if equip_id not in self.batteries:
                            _LOGGER.info("Nouvelle batterie détectée via WebSocket: %s", equip_id)
                            self.batteries[equip_id] = BatteryInfo(equip_id=equip_id)
                            self.known_equip_ids.add(equip_id)
                        
                        # Mettre à jour les données de la batterie
                        battery = self.batteries[equip_id]
                        battery.soc = battery_data.get("soc")
                        battery.temp = battery_data.get("temp")
                        battery.capacity = battery_data.get("capacity")
                        battery.pv1power = battery_data.get("pv1power")
                        battery.pv2power = battery_data.get("pv2power")
                        battery.invPower = battery_data.get("invPower")
                        battery.isWork = battery_data.get("isWork")
                        battery.last_update = current_time
                        
                        # Vérifier si c'est la batterie maître
                        if self.stack_info and equip_id == self.stack_info.main_equip_id:
                            battery.is_master = True
                        
                        _LOGGER.debug("Batterie %s mise à jour: SOC=%s%%, Temp=%s°C, Capacity=%sWh", 
                                    equip_id, battery.soc, battery.temp, battery.capacity)
                        
        except Exception as e:
            _LOGGER.error("Erreur lors de la mise à jour depuis le WebSocket: %s", e)
    
    def get_battery_info(self, equip_id: str) -> Optional[BatteryInfo]:
        """Obtenir les informations d'une batterie spécifique."""
        return self.batteries.get(equip_id)
    
    def get_all_batteries(self) -> Dict[str, BatteryInfo]:
        """Obtenir toutes les batteries."""
        return self.batteries.copy()
    
    def get_master_battery(self) -> Optional[BatteryInfo]:
        """Obtenir la batterie maître."""
        for battery in self.batteries.values():
            if battery.is_master:
                return battery
        return None
    
    def get_stack_info(self) -> Optional[StackInfo]:
        """Obtenir les informations de la pile."""
        return self.stack_info
    
    def get_battery_count(self) -> int:
        """Obtenir le nombre de batteries détectées."""
        return len(self.batteries)
    
    def is_battery_online(self, equip_id: str) -> bool:
        """Vérifier si une batterie est en ligne."""
        battery = self.batteries.get(equip_id)
        if battery:
            # Une batterie est considérée en ligne si elle a des données récentes
            if battery.last_update:
                time_diff = (datetime.now() - battery.last_update).total_seconds()
                return time_diff < 300  # 5 minutes
        return False
    
    def get_online_batteries(self) -> List[str]:
        """Obtenir la liste des batteries en ligne."""
        online_batteries = []
        for equip_id, battery in self.batteries.items():
            if self.is_battery_online(equip_id):
                online_batteries.append(equip_id)
        return online_batteries
    
    def get_total_capacity(self) -> float:
        """Obtenir la capacité totale de toutes les batteries."""
        total = 0.0
        for battery in self.batteries.values():
            if battery.capacity:
                total += battery.capacity
        return total
    
    def get_average_soc(self) -> float:
        """Obtenir le SOC moyen de toutes les batteries."""
        if not self.batteries:
            return 0.0
        
        total_soc = 0.0
        count = 0
        for battery in self.batteries.values():
            if battery.soc is not None:
                total_soc += battery.soc
                count += 1
        
        return total_soc / count if count > 0 else 0.0
    
    def get_average_temperature(self) -> float:
        """Obtenir la température moyenne de toutes les batteries."""
        if not self.batteries:
            return 0.0
        
        total_temp = 0.0
        count = 0
        for battery in self.batteries.values():
            if battery.temp is not None:
                total_temp += battery.temp
                count += 1
        
        return total_temp / count if count > 0 else 0.0
    
    def get_summary(self) -> Dict[str, Any]:
        """Obtenir un résumé de l'état des batteries."""
        return {
            "total_batteries": len(self.batteries),
            "online_batteries": len(self.get_online_batteries()),
            "master_battery": self.get_master_battery().equip_id if self.get_master_battery() else None,
            "total_capacity": self.get_total_capacity(),
            "average_soc": self.get_average_soc(),
            "average_temperature": self.get_average_temperature(),
            "stack_info": {
                "main_equip_id": self.stack_info.main_equip_id if self.stack_info else None,
                "total_pv1power": self.stack_info.total_pv1power if self.stack_info else None,
                "total_pv2power": self.stack_info.total_pv2power if self.stack_info else None,
                "total_inv_power": self.stack_info.total_inv_power if self.stack_info else None,
            } if self.stack_info else None,
            "batteries": {
                equip_id: {
                    "soc": battery.soc,
                    "temp": battery.temp,
                    "capacity": battery.capacity,
                    "is_master": battery.is_master,
                    "is_online": self.is_battery_online(equip_id),
                    "last_update": battery.last_update.isoformat() if battery.last_update else None
                }
                for equip_id, battery in self.batteries.items()
            }
        }
