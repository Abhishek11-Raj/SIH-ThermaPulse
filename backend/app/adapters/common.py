"""Shared adapter helpers. Adapters transform provider-native records into
canonical schemas and attach provenance + quality without losing history."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from ..schemas.common import Provenance, QualityFlag
from ..utils.ids import new_record_id


class BaseAdapter:
    """Common provenance/identity machinery for all adapters."""

    adapter_name: str = "base"
    default_source: str = "mock"

    def source_for(self, raw) -> str:
        """Canonical ``source`` for a raw record.

        A provider that explicitly names its origin (e.g. ``openmeteo``) is
        honored; otherwise the adapter default (``mock``) applies — this keeps
        the deterministic mock path byte-identical to Step 1.
        """
        source = getattr(raw, "source", None)
        provider = getattr(raw, "provider_name", None)
        if source and source != provider:
            return source
        return self.default_source

    def provenance(
        self,
        provider: str,
        source_timestamp: Optional[datetime] = None,
        version: Optional[str] = None,
        quality: QualityFlag = QualityFlag.VALID,
        notes: Optional[List[str]] = None,
        source: Optional[str] = None,
    ) -> Provenance:
        return Provenance(
            source=source or self.default_source,
            provider=provider,
            adapter=self.adapter_name,
            source_timestamp=source_timestamp,
            version=version,
            quality_status=quality,
            notes=notes or [],
        )

    def new_id(self, prefix: str) -> str:
        return new_record_id(prefix)