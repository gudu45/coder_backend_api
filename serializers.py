# proposal/serializers.py

from rest_framework import serializers
from vendor.serializers import VendorSerializer
from .models import Proposal

class ProposalSerializer(serializers.ModelSerializer):
    vendor = VendorSerializer(read_only=True)
    
    class Meta:
        model = Proposal
        fields = [
            'id', 'vendor', 'raw_email_body', 
            'parsed_data', 'is_parsed', 'received_at'
        ]

class SendRFPSerializer(serializers.Serializer):
    vendor_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        help_text="List of vendor IDs to send the RFP to"
    )