# proposal/views.py

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse
from core.models import RFP
from vendor.models import Vendor
from .models import Proposal
from .serializers import ProposalSerializer, SendRFPSerializer
from .services import send_rfp_email, parse_proposal_with_ai, generate_recommendation


@extend_schema(
    summary="Send RFP to selected vendors",
    description="Sends the RFP via email to the specified vendors.",
    request=SendRFPSerializer,
    responses={
        200: OpenApiResponse(description="RFP sent successfully"),
        400: OpenApiResponse(description="Invalid vendor IDs or RFP not found"),
    },
    tags=["Proposals"]
)
@api_view(['POST'])
def send_rfp_to_vendors(request, rfp_id):
    rfp = get_object_or_404(RFP, id=rfp_id)
    serializer = SendRFPSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    vendor_ids = serializer.validated_data['vendor_ids']
    vendors = Vendor.objects.filter(id__in=vendor_ids)

    if len(vendors) != len(vendor_ids):
        return Response(
            {"error": "One or more vendor IDs are invalid."},
            status=status.HTTP_400_BAD_REQUEST
        )

    success_count = 0
    for vendor in vendors:
        if send_rfp_email(rfp, vendor):
            success_count += 1

    rfp.status = "sent"
    rfp.save()

    return Response({
        "detail": f"RFP sent to {success_count} vendor(s)."
    }, status=status.HTTP_200_OK)


@extend_schema(
    summary="Receive vendor proposal (Resend webhook)",
    description=(
        "Webhook endpoint for Resend inbound emails. "
        "Expects email sent to rfp-<ID>@yourdomain.com."
    ),
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'to': {'type': 'array', 'items': {'type': 'string'}},
                'from': {'type': 'string'},
                'text': {'type': 'string'},
                'attachments': {'type': 'array'}
            }
        }
    },
    responses={200: OpenApiResponse(description="Proposal received and parsed")},
    tags=["Proposals"]
)
@api_view(['POST'])
def resend_inbound_webhook(request):
    data = request.data
    to_email = data.get("to", [""])[0]
    
    # Extract RFP ID from email like rfp-123@yourdomain.com
    if not to_email.startswith("rfp-"):
        return Response({"error": "Invalid recipient format"}, status=400)

    try:
        rfp_id = int(to_email.split("rfp-")[1].split("@")[0])
        rfp = RFP.objects.get(id=rfp_id)
    except (ValueError, RFP.DoesNotExist):
        return Response({"error": "RFP not found"}, status=404)

    from_email = data.get("from", "")
    vendor, _ = Vendor.objects.get_or_create(
        email=from_email,
        defaults={"name": from_email.split("@")[0].title()}
    )

    text = data.get("text", "")
    attachments = data.get("attachments", [])

    # Save raw proposal
    proposal, created = Proposal.objects.get_or_create(
        rfp=rfp,
        vendor=vendor,
        defaults={
            "raw_email_body": text,
            "raw_attachments": attachments
        }
    )

    # Parse with AI
    parsed = parse_proposal_with_ai(text)
    proposal.parsed_data = parsed
    proposal.is_parsed = True
    proposal.save()

    return Response({"detail": "Proposal received and parsed"}, status=200)


@extend_schema(
    summary="Compare proposals and get AI recommendation",
    description="Returns all parsed proposals for an RFP plus an AI-generated vendor recommendation.",
    responses={
        200: {
            'type': 'object',
            'properties': {
                'rfp_id': {'type': 'integer'},
                'proposals': {'type': 'array'},
                'ai_recommendation': {
                    'type': 'object',
                    'properties': {
                        'recommendation': {'type': 'string'},
                        'reason': {'type': 'string'}
                    }
                }
            }
        },
        404: OpenApiResponse(description="RFP not found or no proposals")
    },
    tags=["Proposals"]
)
@api_view(['GET'])
def compare_proposals(request, rfp_id):
    rfp = get_object_or_404(RFP, id=rfp_id)
    proposals = Proposal.objects.filter(rfp=rfp, is_parsed=True)

    if not proposals.exists():
        return Response(
            {"error": "No parsed proposals found for this RFP."},
            status=status.HTTP_404_NOT_FOUND
        )

    recommendation = generate_recommendation(rfp, list(proposals))

    return Response({
        "rfp_id": rfp_id,
        "proposals": ProposalSerializer(proposals, many=True).data,
        "ai_recommendation": recommendation
    })