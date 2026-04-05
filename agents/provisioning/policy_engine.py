"""
PolicyEngine — Declarative policy-as-code for Lakebase branch management (GAP-038)

Loads branch_policies.yaml and provides validation/enforcement methods
consumed by BranchingMixin and other provisioning tools.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger("lakebase_ops.provisioning.policy")

# Default path to the policy file, relative to repo root
_DEFAULT_POLICY_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "branch_policies.yaml")


@dataclass
class PolicyViolation:
    """A single policy violation."""

    rule: str
    message: str
    severity: str = "error"  # "error" or "warning"


@dataclass
class PolicyResult:
    """Result of a policy evaluation."""

    allowed: bool
    violations: list[PolicyViolation] = field(default_factory=list)
    warnings: list[PolicyViolation] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "violations": [{"rule": v.rule, "message": v.message} for v in self.violations],
            "warnings": [{"rule": w.rule, "message": w.message} for w in self.warnings],
        }


class PolicyEngine:
    """
    Loads declarative branch policies from YAML and enforces them.

    Usage::

        engine = PolicyEngine()                       # loads default config
        engine = PolicyEngine("/path/to/policies.yaml")  # custom path

        result = engine.check_branch_creation("ci-pr-42", creator_type="ci")
        if not result.allowed:
            raise ValueError(result.violations)
    """

    def __init__(self, policy_path: str | None = None):
        self._path = policy_path or _DEFAULT_POLICY_PATH
        self._policies: dict = {}
        self._load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load policies from YAML file."""
        path = Path(self._path).resolve()
        if not path.exists():
            logger.warning(f"Policy file not found at {path}; using empty policies")
            self._policies = {}
            return

        with open(path) as fh:
            self._policies = yaml.safe_load(fh) or {}

        logger.info(f"Loaded branch policies v{self._policies.get('version', 'unknown')} from {path}")

    def reload(self) -> None:
        """Re-read the policy file (hot-reload)."""
        self._load()

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def naming(self) -> dict:
        return self._policies.get("naming_conventions", {})

    @property
    def ttl_policies(self) -> dict:
        return self._policies.get("ttl_policies", {})

    @property
    def branch_limits(self) -> dict:
        return self._policies.get("branch_limits", {})

    @property
    def protection_rules(self) -> dict:
        return self._policies.get("protection_rules", {})

    @property
    def attribution_config(self) -> dict:
        return self._policies.get("attribution", {})

    @property
    def qa_branch_config(self) -> dict:
        return self._policies.get("qa_branch", {})

    @property
    def nightly_reset_config(self) -> dict:
        return self._policies.get("nightly_reset", {})

    def get_ttl_for_prefix(self, branch_name: str) -> int | None:
        """Return the TTL (seconds) for a branch name based on its prefix."""
        for prefix, ttl in self.ttl_policies.items():
            if branch_name.startswith(prefix):
                return ttl
        return None

    # ------------------------------------------------------------------
    # Validation: branch creation
    # ------------------------------------------------------------------

    def check_branch_creation(
        self,
        branch_name: str,
        current_branch_count: int = 0,
        current_unarchived_count: int = 0,
        creator_type: str = "human",
    ) -> PolicyResult:
        """
        Validate all policies that apply before a branch is created.

        Returns a PolicyResult indicating whether the operation is allowed.
        """
        violations: list[PolicyViolation] = []
        warnings: list[PolicyViolation] = []

        # 1. Naming convention checks
        self._check_naming(branch_name, violations, warnings)

        # 2. Branch limit checks
        self._check_limits(current_branch_count, current_unarchived_count, violations, warnings)

        # 3. Attribution checks
        self._check_attribution(creator_type, violations)

        allowed = len(violations) == 0
        return PolicyResult(allowed=allowed, violations=violations, warnings=warnings)

    # ------------------------------------------------------------------
    # Validation: branch deletion / reset
    # ------------------------------------------------------------------

    def check_branch_deletion(self, branch_name: str) -> PolicyResult:
        """Check whether a branch may be deleted."""
        violations: list[PolicyViolation] = []
        protected = self.protection_rules.get("protected_branches", [])

        if branch_name in protected and self.protection_rules.get("prevent_deletion", True):
            violations.append(
                PolicyViolation(
                    rule="protection_rules.prevent_deletion",
                    message=f"Branch '{branch_name}' is protected and cannot be deleted",
                )
            )

        return PolicyResult(allowed=len(violations) == 0, violations=violations)

    def check_branch_reset(self, branch_name: str, source_branch: str) -> PolicyResult:
        """Check whether a branch reset is allowed."""
        violations: list[PolicyViolation] = []
        warnings: list[PolicyViolation] = []

        allowed_sources = self.protection_rules.get("allowed_reset_sources", {})
        if branch_name in allowed_sources:
            expected_source = allowed_sources[branch_name]
            if source_branch != expected_source:
                violations.append(
                    PolicyViolation(
                        rule="protection_rules.allowed_reset_sources",
                        message=(
                            f"Branch '{branch_name}' can only be reset from '{expected_source}', not '{source_branch}'"
                        ),
                    )
                )

        protected = self.protection_rules.get("protected_branches", [])
        if branch_name in protected and self.protection_rules.get("prevent_reset_without_approval", True):
            warnings.append(
                PolicyViolation(
                    rule="protection_rules.prevent_reset_without_approval",
                    message=f"Resetting protected branch '{branch_name}' requires approval",
                    severity="warning",
                )
            )

        return PolicyResult(
            allowed=len(violations) == 0,
            violations=violations,
            warnings=warnings,
        )

    def check_direct_migration(self, branch_name: str) -> PolicyResult:
        """Check whether direct schema migration is allowed on a branch."""
        violations: list[PolicyViolation] = []
        protected = self.protection_rules.get("protected_branches", [])

        if branch_name in protected and self.protection_rules.get("prevent_direct_migration", True):
            violations.append(
                PolicyViolation(
                    rule="protection_rules.prevent_direct_migration",
                    message=(
                        f"Direct schema migration on protected branch '{branch_name}' "
                        f"is not allowed. Use an ephemeral branch and promote."
                    ),
                )
            )

        return PolicyResult(allowed=len(violations) == 0, violations=violations)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_naming(
        self,
        branch_name: str,
        violations: list[PolicyViolation],
        warnings: list[PolicyViolation],
    ) -> None:
        naming = self.naming
        if not naming:
            return

        max_len = naming.get("max_length", 63)
        min_len = naming.get("min_length", 3)
        pattern = naming.get("allowed_pattern", "")

        if len(branch_name) > max_len:
            violations.append(
                PolicyViolation(
                    rule="naming_conventions.max_length",
                    message=f"Branch name '{branch_name}' exceeds max length of {max_len}",
                )
            )

        if len(branch_name) < min_len:
            violations.append(
                PolicyViolation(
                    rule="naming_conventions.min_length",
                    message=f"Branch name '{branch_name}' is shorter than min length of {min_len}",
                )
            )

        if pattern and not re.match(pattern, branch_name):
            violations.append(
                PolicyViolation(
                    rule="naming_conventions.allowed_pattern",
                    message=(f"Branch name '{branch_name}' does not match RFC 1123 pattern: {pattern}"),
                )
            )

        # Check that a known prefix is used
        prefixes = naming.get("prefixes", {})
        if prefixes:
            has_prefix = any(branch_name.startswith(p) for p in prefixes)
            # Protected branches (production, staging) are always allowed
            protected = self.protection_rules.get("protected_branches", [])
            if not has_prefix and branch_name not in protected:
                warnings.append(
                    PolicyViolation(
                        rule="naming_conventions.prefixes",
                        message=(
                            f"Branch name '{branch_name}' does not start with a known "
                            f"prefix ({', '.join(sorted(prefixes))})"
                        ),
                        severity="warning",
                    )
                )

    def _check_limits(
        self,
        current_count: int,
        current_unarchived: int,
        violations: list[PolicyViolation],
        warnings: list[PolicyViolation],
    ) -> None:
        limits = self.branch_limits
        if not limits:
            return

        max_total = limits.get("max_branches_per_project", 500)
        max_unarchived = limits.get("max_unarchived_branches", 10)
        warn_pct = limits.get("warning_threshold_pct", 80)
        crit_pct = limits.get("critical_threshold_pct", 90)

        # Hard limit: unarchived branches
        if current_unarchived >= max_unarchived:
            violations.append(
                PolicyViolation(
                    rule="branch_limits.max_unarchived_branches",
                    message=(
                        f"Cannot create branch: {current_unarchived}/{max_unarchived} unarchived branches already exist"
                    ),
                )
            )

        # Hard limit: total branches
        if current_count >= max_total:
            violations.append(
                PolicyViolation(
                    rule="branch_limits.max_branches_per_project",
                    message=(f"Cannot create branch: {current_count}/{max_total} total branches already exist"),
                )
            )

        # Soft warning thresholds
        utilization = (current_unarchived / max_unarchived * 100) if max_unarchived else 0
        if utilization >= crit_pct and current_unarchived < max_unarchived:
            warnings.append(
                PolicyViolation(
                    rule="branch_limits.critical_threshold",
                    message=f"Branch utilization at {utilization:.0f}% (critical threshold: {crit_pct}%)",
                    severity="warning",
                )
            )
        elif utilization >= warn_pct:
            warnings.append(
                PolicyViolation(
                    rule="branch_limits.warning_threshold",
                    message=f"Branch utilization at {utilization:.0f}% (warning threshold: {warn_pct}%)",
                    severity="warning",
                )
            )

    def _check_attribution(
        self,
        creator_type: str,
        violations: list[PolicyViolation],
    ) -> None:
        attr = self.attribution_config
        if not attr or not attr.get("required", False):
            return

        valid_types = attr.get("valid_creator_types", ["human", "agent", "ci"])
        if creator_type not in valid_types:
            violations.append(
                PolicyViolation(
                    rule="attribution.valid_creator_types",
                    message=(f"Invalid creator_type '{creator_type}'. Must be one of: {', '.join(valid_types)}"),
                )
            )
