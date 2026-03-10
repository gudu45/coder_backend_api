# proposal/models.py

from django.db import models
from core.models import RFP
from vendor.models import Vendor

class Proposal(models.Model):
    rfp = models.ForeignKey(RFP, on_delete=models.CASCADE, related_name="proposals")
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    raw_email_body = models.TextField(blank=True)
    raw_attachments = models.JSONField(default=list)  # e.g., ["quote.pdf"]
    parsed_data = models.JSONField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    is_parsed = models.BooleanField(default=False)

    def __str__(self):
        return f"Proposal from {self.vendor.name} for {self.rfp.title}"

    class Meta:
        unique_together = ('rfp', 'vendor')  # One proposal per vendor per RFP
        ordering = ['-received_at']