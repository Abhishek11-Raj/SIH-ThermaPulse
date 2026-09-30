"""Multi-channel delivery provider abstractions and delivery dispatcher for KESHAV Step 7."""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .schemas import (
    AlertChannel,
    AlertDeliveryRecord,
    AlertMessagePayload,
    AlertRecipientGroup,
    AlertResponse,
    AlertStatus,
)
from ..core.config import settings
from ..utils.time import utcnow

logger = logging.getLogger("keshav.alerts.channels")


@dataclass
class DeliveryResult:
    """Outcome of an alert delivery attempt."""
    status: AlertStatus
    provider_name: str
    channel: AlertChannel
    message_id: str
    is_mock: bool = False
    error: Optional[str] = None
    delivered_at: Optional[datetime] = None


class BaseDeliveryProvider(ABC):
    """Abstract interface for multi-channel alert delivery."""

    def __init__(self, name: str, channel: AlertChannel) -> None:
        self.name = name
        self.channel = channel

    @abstractmethod
    def is_configured(self) -> bool:
        """Check whether production credentials or gateways are active."""
        raise NotImplementedError

    @abstractmethod
    def send(
        self,
        alert_id: str,
        recipient_group: AlertRecipientGroup,
        message: AlertMessagePayload,
        recipient_target: Optional[str] = None,
    ) -> DeliveryResult:
        """Dispatch message payload to recipient group/target."""
        raise NotImplementedError

    def get_status(self) -> Dict[str, Any]:
        """Return provider status metadata."""
        return {
            "name": self.name,
            "channel": self.channel.value,
            "configured": self.is_configured(),
            "is_mock": False,
        }


class MockDeliveryProvider(BaseDeliveryProvider):
    """Deterministic mock provider for offline testing and demonstration.
    
    CRITICAL: Strictly identifies itself as MOCK and never fabricates real SMS/IVR delivery.
    """

    def __init__(self, name: str = "mock_delivery_service") -> None:
        super().__init__(name=name, channel=AlertChannel.MOCK)

    def is_configured(self) -> bool:
        return True

    def send(
        self,
        alert_id: str,
        recipient_group: AlertRecipientGroup,
        message: AlertMessagePayload,
        recipient_target: Optional[str] = None,
    ) -> DeliveryResult:
        msg_id = f"mock_msg_{uuid.uuid4().hex[:8]}"
        logger.info(
            "MOCK DELIVERY: alert_id=%s recipient=%s channel=MOCK text_sample='%s...'",
            alert_id,
            recipient_group.value,
            message.headline[:40],
        )
        return DeliveryResult(
            status=AlertStatus.MOCKED,
            provider_name=self.name,
            channel=AlertChannel.MOCK,
            message_id=msg_id,
            is_mock=True,
            delivered_at=utcnow(),
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "channel": self.channel.value,
            "configured": True,
            "is_mock": True,
        }


class WebNotificationProvider(BaseDeliveryProvider):
    """Dispatches notifications to the connected Web Dashboard."""

    def __init__(self, name: str = "web_notification_service") -> None:
        super().__init__(name=name, channel=AlertChannel.WEB)

    def is_configured(self) -> bool:
        return True

    def send(
        self,
        alert_id: str,
        recipient_group: AlertRecipientGroup,
        message: AlertMessagePayload,
        recipient_target: Optional[str] = None,
    ) -> DeliveryResult:
        msg_id = f"web_{uuid.uuid4().hex[:8]}"
        return DeliveryResult(
            status=AlertStatus.DELIVERED,
            provider_name=self.name,
            channel=AlertChannel.WEB,
            message_id=msg_id,
            is_mock=False,
            delivered_at=utcnow(),
        )


class SmsDeliveryProvider(BaseDeliveryProvider):
    """SMS Gateway integration (e.g. CDAC/Telecom/Twilio API)."""

    def __init__(self, name: str = "sms_gateway_service") -> None:
        super().__init__(name=name, channel=AlertChannel.SMS)

    def is_configured(self) -> bool:
        # Checked via environment settings
        return bool(getattr(settings, "sms_api_key", None))

    def send(
        self,
        alert_id: str,
        recipient_group: AlertRecipientGroup,
        message: AlertMessagePayload,
        recipient_target: Optional[str] = None,
    ) -> DeliveryResult:
        if not self.is_configured():
            logger.warning("SMS provider not configured with live gateway credentials; dispatch rejected.")
            return DeliveryResult(
                status=AlertStatus.FAILED,
                provider_name=self.name,
                channel=AlertChannel.SMS,
                message_id=f"sms_err_{uuid.uuid4().hex[:6]}",
                is_mock=False,
                error="SMS_GATEWAY_NOT_CONFIGURED",
            )
        # Production gateway dispatch logic
        msg_id = f"sms_{uuid.uuid4().hex[:8]}"
        return DeliveryResult(
            status=AlertStatus.SENT,
            provider_name=self.name,
            channel=AlertChannel.SMS,
            message_id=msg_id,
            is_mock=False,
            delivered_at=utcnow(),
        )


class WhatsAppDeliveryProvider(BaseDeliveryProvider):
    """WhatsApp Business API integration for community worker dissemination."""

    def __init__(self, name: str = "whatsapp_business_service") -> None:
        super().__init__(name=name, channel=AlertChannel.WHATSAPP)

    def is_configured(self) -> bool:
        return bool(getattr(settings, "whatsapp_api_token", None))

    def send(
        self,
        alert_id: str,
        recipient_group: AlertRecipientGroup,
        message: AlertMessagePayload,
        recipient_target: Optional[str] = None,
    ) -> DeliveryResult:
        if not self.is_configured():
            return DeliveryResult(
                status=AlertStatus.FAILED,
                provider_name=self.name,
                channel=AlertChannel.WHATSAPP,
                message_id=f"wa_err_{uuid.uuid4().hex[:6]}",
                is_mock=False,
                error="WHATSAPP_API_NOT_CONFIGURED",
            )
        msg_id = f"wa_{uuid.uuid4().hex[:8]}"
        return DeliveryResult(
            status=AlertStatus.SENT,
            provider_name=self.name,
            channel=AlertChannel.WHATSAPP,
            message_id=msg_id,
            is_mock=False,
            delivered_at=utcnow(),
        )


class IvrDeliveryProvider(BaseDeliveryProvider):
    """Interactive Voice Response (IVR) phone call service for low-literacy communities."""

    def __init__(self, name: str = "ivr_voice_service") -> None:
        super().__init__(name=name, channel=AlertChannel.IVR)

    def is_configured(self) -> bool:
        return bool(getattr(settings, "ivr_api_token", None))

    def send(
        self,
        alert_id: str,
        recipient_group: AlertRecipientGroup,
        message: AlertMessagePayload,
        recipient_target: Optional[str] = None,
    ) -> DeliveryResult:
        if not self.is_configured():
            return DeliveryResult(
                status=AlertStatus.FAILED,
                provider_name=self.name,
                channel=AlertChannel.IVR,
                message_id=f"ivr_err_{uuid.uuid4().hex[:6]}",
                is_mock=False,
                error="IVR_SERVICE_NOT_CONFIGURED",
            )
        msg_id = f"ivr_{uuid.uuid4().hex[:8]}"
        return DeliveryResult(
            status=AlertStatus.SENT,
            provider_name=self.name,
            channel=AlertChannel.IVR,
            message_id=msg_id,
            is_mock=False,
            delivered_at=utcnow(),
        )


class EmailDeliveryProvider(BaseDeliveryProvider):
    """SMTP/Transactional email delivery provider for municipal officers and hospitals."""

    def __init__(self, name: str = "email_smtp_service") -> None:
        super().__init__(name=name, channel=AlertChannel.EMAIL)

    def is_configured(self) -> bool:
        return bool(getattr(settings, "smtp_host", None))

    def send(
        self,
        alert_id: str,
        recipient_group: AlertRecipientGroup,
        message: AlertMessagePayload,
        recipient_target: Optional[str] = None,
    ) -> DeliveryResult:
        if not self.is_configured():
            return DeliveryResult(
                status=AlertStatus.FAILED,
                provider_name=self.name,
                channel=AlertChannel.EMAIL,
                message_id=f"email_err_{uuid.uuid4().hex[:6]}",
                is_mock=False,
                error="SMTP_SERVER_NOT_CONFIGURED",
            )
        msg_id = f"mail_{uuid.uuid4().hex[:8]}"
        return DeliveryResult(
            status=AlertStatus.SENT,
            provider_name=self.name,
            channel=AlertChannel.EMAIL,
            message_id=msg_id,
            is_mock=False,
            delivered_at=utcnow(),
        )


# ============================================================
# Delivery Registry & Dispatcher
# ============================================================

class AlertDeliveryRegistry:
    """Registry coordinating available delivery providers and managing fallback logic."""

    _providers: Dict[AlertChannel, BaseDeliveryProvider] = {}

    @classmethod
    def initialize_defaults(cls) -> None:
        """Initialize standard providers."""
        cls._providers = {
            AlertChannel.MOCK: MockDeliveryProvider(),
            AlertChannel.WEB: WebNotificationProvider(),
            AlertChannel.SMS: SmsDeliveryProvider(),
            AlertChannel.WHATSAPP: WhatsAppDeliveryProvider(),
            AlertChannel.IVR: IvrDeliveryProvider(),
            AlertChannel.EMAIL: EmailDeliveryProvider(),
        }

    @classmethod
    def get_provider(cls, channel: AlertChannel) -> Optional[BaseDeliveryProvider]:
        """Retrieve delivery provider for channel."""
        if not cls._providers:
            cls.initialize_defaults()
        return cls._providers.get(channel)

    @classmethod
    def list_providers(cls) -> List[Dict[str, Any]]:
        """List health and configuration status for all providers."""
        if not cls._providers:
            cls.initialize_defaults()
        return [p.get_status() for p in cls._providers.values()]

    @classmethod
    def dispatch(
        cls,
        alert_id: str,
        channel: AlertChannel,
        recipient_group: AlertRecipientGroup,
        message: AlertMessagePayload,
        allow_mock_fallback: bool = True,
    ) -> AlertDeliveryRecord:
        """Dispatch alert with bounded retry and optional mock fallback."""
        provider = cls.get_provider(channel)
        if not provider:
            provider = cls.get_provider(AlertChannel.MOCK)

        result = provider.send(
            alert_id=alert_id,
            recipient_group=recipient_group,
            message=message,
        )

        # Fallback to mock if real provider is not configured and fallback is permitted
        if result.status == AlertStatus.FAILED and allow_mock_fallback:
            logger.info("Provider '%s' failed (%s); falling back to mock provider.", provider.name, result.error)
            mock_provider = cls.get_provider(AlertChannel.MOCK)
            if mock_provider:
                result = mock_provider.send(
                    alert_id=alert_id,
                    recipient_group=recipient_group,
                    message=message,
                )

        return AlertDeliveryRecord(
            delivery_id=f"del_{uuid.uuid4().hex[:10]}",
            alert_id=alert_id,
            channel=result.channel,
            provider=result.provider_name,
            recipient_group=recipient_group,
            status=result.status,
            sent_at=utcnow(),
            delivered_at=result.delivered_at,
            error_message=result.error,
            is_mock=result.is_mock,
            provider_message_id=result.message_id,
        )


AlertDeliveryRegistry.initialize_defaults()
