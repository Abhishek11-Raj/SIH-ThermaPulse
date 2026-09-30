"""KESHAV STEP 7: Alert Channel Abstraction.

Provider abstraction for alert delivery channels.
Supports WEB, SMS, WHATSAPP, IVR, EMAIL, MOCK.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from ..alert.schemas import (
    AlertChannel,
    AlertDelivery,
    AlertMessage,
    DeliveryResult,
    RecipientGroup,
)


class AlertChannelProvider(ABC):
    """Abstract base class for alert channel providers."""

    @property
    @abstractmethod
    def channel(self) -> AlertChannel:
        """Return the channel this provider supports."""

    @abstractmethod
    def send(
        self,
        message: AlertMessage,
        recipient: str,
        recipient_group: RecipientGroup,
    ) -> AlertDelivery:
        """Send an alert message.

        Returns an AlertDelivery record with the result.
        """

    @abstractmethod
    def supports_acknowledgement(self) -> bool:
        """Whether this channel supports acknowledgement."""

    @abstractmethod
    def get_delivery_status(self, delivery_id: str) -> Optional[AlertDelivery]:
        """Get the status of a delivery."""


class MockProvider(AlertChannelProvider):
    """Deterministic MOCK provider for development/testing.

    NEVER claims real delivery. Always returns MOCKED.
    Explicitly labeled as mock in all outputs.
    """

    @property
    def channel(self) -> AlertChannel:
        return AlertChannel.MOCK

    def send(
        self,
        message: AlertMessage,
        recipient: str,
        recipient_group: RecipientGroup,
    ) -> AlertDelivery:
        """Mock send - always returns MOCKED result."""
        delivery = AlertDelivery(
            delivery_id=f"mock_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
            alert_id=message.alert_id,
            channel=AlertChannel.MOCK,
            recipient_group=recipient_group,
            result=DeliveryResult.MOCKED,
            message=f"MOCK: {message.subject}",
            provider_name="mock",
            completed_at=datetime.utcnow(),
        )
        return delivery

    def supports_acknowledgement(self) -> bool:
        return False

    def get_delivery_status(self, delivery_id: str) -> Optional[AlertDelivery]:
        return None


class WebProvider(AlertChannelProvider):
    """WEB channel provider.

    In a real implementation, this would push to a webhook
    or frontend notification system.
    """

    @property
    def channel(self) -> AlertChannel:
        return AlertChannel.WEB

    def send(
        self,
        message: AlertMessage,
        recipient: str,
        recipient_group: RecipientGroup,
    ) -> AlertDelivery:
        """Send via web channel."""
        delivery = AlertDelivery(
            delivery_id=f"web_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
            alert_id=message.alert_id,
            channel=AlertChannel.WEB,
            recipient_group=recipient_group,
            result=DeliveryResult.SENT,
            message=message.subject,
            provider_name="web",
            completed_at=datetime.utcnow(),
        )
        return delivery

    def supports_acknowledgement(self) -> bool:
        return True

    def get_delivery_status(self, delivery_id: str) -> Optional[AlertDelivery]:
        return None


class SmsProvider(AlertChannelProvider):
    """SMS channel provider.

    Requires real provider credentials configured via environment.
    Without credentials, returns UNSUPPORTED.
    """

    @property
    def channel(self) -> AlertChannel:
        return AlertChannel.SMS

    def send(
        self,
        message: AlertMessage,
        recipient: str,
        recipient_group: RecipientGroup,
    ) -> AlertDelivery:
        """Send via SMS. Returns UNSUPPORTED without real credentials."""
        return AlertDelivery(
            delivery_id=f"sms_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
            alert_id=message.alert_id,
            channel=AlertChannel.SMS,
            recipient_group=recipient_group,
            result=DeliveryResult.UNSUPPORTED,
            message="SMS provider not configured",
            provider_name="sms",
            completed_at=datetime.utcnow(),
        )

    def supports_acknowledgement(self) -> bool:
        return False

    def get_delivery_status(self, delivery_id: str) -> Optional[AlertDelivery]:
        return None


class WhatsAppProvider(AlertChannelProvider):
    """WhatsApp channel provider."""

    @property
    def channel(self) -> AlertChannel:
        return AlertChannel.WHATSAPP

    def send(
        self,
        message: AlertMessage,
        recipient: str,
        recipient_group: RecipientGroup,
    ) -> AlertDelivery:
        return AlertDelivery(
            delivery_id=f"wa_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
            alert_id=message.alert_id,
            channel=AlertChannel.WHATSAPP,
            recipient_group=recipient_group,
            result=DeliveryResult.UNSUPPORTED,
            message="WhatsApp provider not configured",
            provider_name="whatsapp",
            completed_at=datetime.utcnow(),
        )

    def supports_acknowledgement(self) -> bool:
        return False

    def get_delivery_status(self, delivery_id: str) -> Optional[AlertDelivery]:
        return None


class IvrProvider(AlertChannelProvider):
    """IVR channel provider."""

    @property
    def channel(self) -> AlertChannel:
        return AlertChannel.IVR

    def send(
        self,
        message: AlertMessage,
        recipient: str,
        recipient_group: RecipientGroup,
    ) -> AlertDelivery:
        return AlertDelivery(
            delivery_id=f"ivr_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
            alert_id=message.alert_id,
            channel=AlertChannel.IVR,
            recipient_group=recipient_group,
            result=DeliveryResult.UNSUPPORTED,
            message="IVR provider not configured",
            provider_name="ivr",
            completed_at=datetime.utcnow(),
        )

    def supports_acknowledgement(self) -> bool:
        return False

    def get_delivery_status(self, delivery_id: str) -> Optional[AlertDelivery]:
        return None


class EmailProvider(AlertChannelProvider):
    """Email channel provider."""

    @property
    def channel(self) -> AlertChannel:
        return AlertChannel.EMAIL

    def send(
        self,
        message: AlertMessage,
        recipient: str,
        recipient_group: RecipientGroup,
    ) -> AlertDelivery:
        return AlertDelivery(
            delivery_id=f"email_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
            alert_id=message.alert_id,
            channel=AlertChannel.EMAIL,
            recipient_group=recipient_group,
            result=DeliveryResult.UNSUPPORTED,
            message="Email provider not configured",
            provider_name="email",
            completed_at=datetime.utcnow(),
        )

    def supports_acknowledgement(self) -> bool:
        return True

    def get_delivery_status(self, delivery_id: str) -> Optional[AlertDelivery]:
        return None


# Provider registry
_PROVIDERS: dict = {
    AlertChannel.MOCK: MockProvider,
    AlertChannel.WEB: WebProvider,
    AlertChannel.SMS: SmsProvider,
    AlertChannel.WHATSAPP: WhatsAppProvider,
    AlertChannel.IVR: IvrProvider,
    AlertChannel.EMAIL: EmailProvider(),
}


def get_provider(channel: AlertChannel) -> AlertChannelProvider:
    """Get a provider for the given channel."""
    provider_class = _PROVIDERS.get(channel)
    if provider_class is None:
        raise ValueError(f"Unsupported channel: {channel}")
    if isinstance(provider_class, AlertChannelProvider):
        return provider_class
    return provider_class()