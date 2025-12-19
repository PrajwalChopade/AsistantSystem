"""
Human support agent pool - loads agents from configuration file.
No Redis dependency for agent management.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from app.config import settings


class AgentStatus(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


@dataclass
class HumanAgent:
    """Human support agent."""
    agent_id: str
    name: str
    email: str
    status: str = AgentStatus.AVAILABLE.value
    specializations: List[str] = field(default_factory=lambda: ["general"])
    current_load: int = 0
    max_load: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "email": self.email,
            "status": self.status,
            "specializations": self.specializations,
        }

    @property
    def is_available(self) -> bool:
        return self.status == AgentStatus.AVAILABLE.value and self.current_load < self.max_load


class HumanAgentPool:
    """
    Manages human support agents loaded from configuration file.
    
    Reads agent details from HumanAssistants.txt in the client's document folder.
    Format: Name : name, Email : email (one agent per pair of lines)
    """
    
    def __init__(self):
        self._agents: Dict[str, HumanAgent] = {}
        self._load_default_agents()
    
    def _load_default_agents(self):
        """Load agents from default location."""
        default_path = settings.DOCUMENTS_DIR / "demo_client" / "HumanAssistants.txt"
        if default_path.exists():
            self._load_agents_from_file(default_path)
    
    def _load_agents_from_file(self, file_path: Path) -> List[HumanAgent]:
        """
        Parse HumanAssistants.txt file.
        
        Expected format:
            Name : Prajwal Chopade
            Email : prajwal443101@gmail.com
        """
        agents = []
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            lines = [line.strip() for line in content.split("\n") if line.strip()]
            
            name = None
            email = None
            
            for line in lines:
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if key == "name":
                        name = value
                    elif key == "email":
                        email = value
                
                if name and email:
                    agent_id = f"agent_{len(self._agents) + 1:03d}"
                    agent = HumanAgent(
                        agent_id=agent_id,
                        name=name,
                        email=email,
                        status=AgentStatus.AVAILABLE.value,
                        specializations=["general", "billing", "technical"]
                    )
                    self._agents[agent_id] = agent
                    agents.append(agent)
                    print(f"✅ Loaded support agent: {name} ({email})")
                    name = None
                    email = None
            
        except Exception as e:
            print(f"⚠️ Could not load agents from {file_path}: {e}")
        
        return agents
    
    def load_client_agents(self, client_id: str) -> List[HumanAgent]:
        """Load agents specific to a client."""
        client_path = settings.DOCUMENTS_DIR / client_id / "HumanAssistants.txt"
        if client_path.exists():
            return self._load_agents_from_file(client_path)
        return []
    
    def get_agent(self, agent_id: str) -> Optional[HumanAgent]:
        return self._agents.get(agent_id)
    
    def get_all_agents(self) -> List[HumanAgent]:
        return list(self._agents.values())
    
    def get_available_agents(self, specialization: Optional[str] = None) -> List[HumanAgent]:
        """Get available agents, optionally filtered by specialization."""
        available = [a for a in self._agents.values() if a.is_available]
        
        if specialization:
            specialized = [a for a in available if specialization in a.specializations]
            if specialized:
                return specialized
        
        return available
    
    def assign_agent(
        self,
        user_id: str,
        specialization: Optional[str] = None,
        severity: str = "low"
    ) -> Optional[HumanAgent]:
        """
        Assign an available agent to handle a request.
        Returns the agent with lowest current load.
        """
        available = self.get_available_agents(specialization)
        
        if not available:
            if severity == "high" and self._agents:
                return list(self._agents.values())[0]
            return None
        
        available.sort(key=lambda a: a.current_load)
        agent = available[0]
        agent.current_load += 1
        
        return agent
    
    def release_agent(self, agent_id: str) -> bool:
        """Release an agent after request is handled."""
        agent = self._agents.get(agent_id)
        if agent and agent.current_load > 0:
            agent.current_load -= 1
            return True
        return False


_pool: Optional[HumanAgentPool] = None


def get_human_pool() -> HumanAgentPool:
    """Get the human agent pool singleton."""
    global _pool
    if _pool is None:
        _pool = HumanAgentPool()
    return _pool


def seed_demo_agents():
    """No-op for compatibility - agents loaded from file."""
    pool = get_human_pool()
    if not pool.get_all_agents():
        print("⚠️ No agents loaded. Add HumanAssistants.txt to documents folder.")
