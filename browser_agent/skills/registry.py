"""
Skill Registry Module

Provides a registry for skill registration and discovery.
"""

from typing import Any, Dict, List, Optional, Type, Set
import logging

from .base import BaseSkill, SkillCapability

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Registry for skill management.

    Allows registration, discovery, and instantiation of skills.
    Supports capability-based skill lookup.
    """

    def __init__(self):
        """Initialize the skill registry."""
        self._skills: Dict[str, Type[BaseSkill]] = {}
        self._instances: Dict[str, BaseSkill] = {}
        self._capability_index: Dict[SkillCapability, Set[str]] = {cap: set() for cap in SkillCapability}
        self._logger = logging.getLogger(__name__)

    def register(self, skill_class: Type[BaseSkill]) -> Type[BaseSkill]:
        """
        Register a skill class.

        Can be used as a decorator:
            @registry.register
            class MySkill(BaseSkill):
                ...

        Args:
            skill_class: The skill class to register

        Returns:
            The registered skill class

        Raises:
            ValueError: If skill name is already registered
        """
        name = skill_class.name

        if name in self._skills:
            self._logger.warning(f"Overwriting existing skill: {name}")

        self._skills[name] = skill_class

        # Index by capabilities
        for cap in skill_class.required_capabilities:
            self._capability_index[cap].add(name)

        self._logger.info(f"Registered skill: {name} v{skill_class.version}")
        return skill_class

    def unregister(self, name: str) -> bool:
        """
        Unregister a skill.

        Args:
            name: Name of the skill to unregister

        Returns:
            True if skill was unregistered, False if not found
        """
        if name not in self._skills:
            return False

        skill_class = self._skills[name]

        # Remove from capability index
        for cap in skill_class.required_capabilities:
            self._capability_index[cap].discard(name)

        # Remove from registry
        del self._skills[name]

        # Remove instance if exists
        if name in self._instances:
            del self._instances[name]

        self._logger.info(f"Unregistered skill: {name}")
        return True

    def get_skill_class(self, name: str) -> Optional[Type[BaseSkill]]:
        """
        Get a skill class by name.

        Args:
            name: Name of the skill

        Returns:
            Skill class or None if not found
        """
        return self._skills.get(name)

    def get_skill(
        self,
        name: str,
        browser_controller: Any = None,
        vision_client: Any = None,
        action_executor: Any = None,
        recovery_manager: Any = None,
        config: Optional[Dict[str, Any]] = None,
        reuse_instance: bool = True,
    ) -> Optional[BaseSkill]:
        """
        Get or create a skill instance.

        Args:
            name: Name of the skill
            browser_controller: Browser controller instance
            vision_client: Vision client instance
            action_executor: Action executor instance
            recovery_manager: Recovery manager instance
            config: Optional configuration dictionary
            reuse_instance: Whether to reuse existing instance

        Returns:
            Skill instance or None if not found
        """
        skill_class = self.get_skill_class(name)
        if skill_class is None:
            self._logger.warning(f"Skill not found: {name}")
            return None

        if reuse_instance and name in self._instances:
            return self._instances[name]

        instance = skill_class(
            browser_controller=browser_controller,
            vision_client=vision_client,
            action_executor=action_executor,
            recovery_manager=recovery_manager,
            config=config,
        )

        if reuse_instance:
            self._instances[name] = instance

        return instance

    def list_skills(self) -> List[str]:
        """
        List all registered skill names.

        Returns:
            List of skill names
        """
        return list(self._skills.keys())

    def get_skills_by_capability(
        self,
        capability: SkillCapability,
    ) -> List[str]:
        """
        Get skills that require a specific capability.

        Args:
            capability: Required capability

        Returns:
            List of skill names requiring the capability
        """
        return list(self._capability_index.get(capability, set()))

    def get_skills_for_capabilities(
        self,
        required_capabilities: Set[SkillCapability],
    ) -> List[str]:
        """
        Get skills that provide all required capabilities.

        Args:
            required_capabilities: Set of required capabilities

        Returns:
            List of skill names providing all capabilities
        """
        result = []

        for name, skill_class in self._skills.items():
            provided = skill_class.provided_capabilities
            if required_capabilities.issubset(provided):
                result.append(name)

        return result

    def get_skill_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a skill.

        Args:
            name: Name of the skill

        Returns:
            Dictionary with skill information or None if not found
        """
        skill_class = self.get_skill_class(name)
        if skill_class is None:
            return None

        return {
            "name": skill_class.name,
            "description": skill_class.description,
            "version": skill_class.version,
            "required_capabilities": [c.value for c in skill_class.required_capabilities],
            "provided_capabilities": [c.value for c in skill_class.provided_capabilities],
        }

    def clear(self) -> None:
        """Clear all registered skills."""
        self._skills.clear()
        self._instances.clear()
        for cap in self._capability_index:
            self._capability_index[cap].clear()
        self._logger.info("Cleared all skills from registry")

    def __contains__(self, name: str) -> bool:
        """Check if a skill is registered."""
        return name in self._skills

    def __len__(self) -> int:
        """Get number of registered skills."""
        return len(self._skills)

    def __repr__(self) -> str:
        return f"SkillRegistry(skills={len(self._skills)})"


# Global registry instance
_global_registry: Optional[SkillRegistry] = None


def get_global_registry() -> SkillRegistry:
    """
    Get the global skill registry.

    Creates the registry on first access.

    Returns:
        Global SkillRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry


def register_skill(skill_class: Type[BaseSkill]) -> Type[BaseSkill]:
    """
    Register a skill with the global registry.

    Convenience function for decorator usage.

    Args:
        skill_class: The skill class to register

    Returns:
        The registered skill class
    """
    return get_global_registry().register(skill_class)
