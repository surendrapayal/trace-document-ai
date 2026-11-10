from google.cloud import dlp_v2
from trace_ai.config import config
from trace_ai.common.logging_client import log

_PII_INFO_TYPES = [
    {"name": "PERSON_NAME"},
    {"name": "DATE_OF_BIRTH"},
    {"name": "US_SOCIAL_SECURITY_NUMBER"},
    {"name": "US_DRIVERS_LICENSE_NUMBER"},
    {"name": "PHONE_NUMBER"},
    {"name": "EMAIL_ADDRESS"},
    {"name": "STREET_ADDRESS"},
    {"name": "US_BANK_ROUTING_MICR"},
    {"name": "FINANCIAL_ACCOUNT_NUMBER"},
]

_MASK_CHAR = "*"


def mask_pii(text: str, contract_id: str) -> tuple[str, list[str]]:
    client = dlp_v2.DlpServiceClient()
    parent = f"projects/{config.GCP_PROJECT_ID}/locations/global"

    item = dlp_v2.ContentItem(value=text)
    inspect_config = dlp_v2.InspectConfig(info_types=_PII_INFO_TYPES, min_likelihood=dlp_v2.Likelihood.LIKELY)
    deidentify_config = dlp_v2.DeidentifyConfig(
        info_type_transformations=dlp_v2.InfoTypeTransformations(
            transformations=[
                dlp_v2.InfoTypeTransformations.InfoTypeTransformation(
                    primitive_transformation=dlp_v2.PrimitiveTransformation(
                        character_mask_config=dlp_v2.CharacterMaskConfig(
                            masking_character=_MASK_CHAR,
                            number_to_mask=0,
                        )
                    )
                )
            ]
        )
    )

    response = client.deidentify_content(
        request=dlp_v2.DeidentifyContentRequest(
            parent=parent,
            deidentify_config=deidentify_config,
            inspect_config=inspect_config,
            item=item,
        )
    )

    inspect_response = client.inspect_content(
        request=dlp_v2.InspectContentRequest(
            parent=parent,
            inspect_config=inspect_config,
            item=item,
        )
    )
    detected_types = list({f.info_type.name for f in inspect_response.result.findings})

    log(
        "extraction",
        contract_id,
        "DLP masking complete",
        pii_types_detected=detected_types,
        findings_count=len(inspect_response.result.findings),
    )

    return response.item.value, detected_types
