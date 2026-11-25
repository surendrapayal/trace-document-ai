from google.cloud import dlp_v2
from trace_ai.config import config
from trace_ai.common.logger import log

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


def _inspect_config() -> dlp_v2.InspectConfig | None:
    """Returns None when a stored inspect template is used instead."""
    if config.DLP_INSPECT_TEMPLATE_NAME:
        return None
    return dlp_v2.InspectConfig(
        info_types=_PII_INFO_TYPES,
        min_likelihood=dlp_v2.Likelihood[config.DLP_MIN_LIKELIHOOD],
    )


def _deidentify_config() -> dlp_v2.DeidentifyConfig | None:
    """Returns None when a stored deidentify template is used instead."""
    if config.DLP_DEIDENTIFY_TEMPLATE_NAME:
        return None
    return dlp_v2.DeidentifyConfig(
        info_type_transformations=dlp_v2.InfoTypeTransformations(
            transformations=[
                dlp_v2.InfoTypeTransformations.InfoTypeTransformation(
                    primitive_transformation=dlp_v2.PrimitiveTransformation(
                        character_mask_config=dlp_v2.CharacterMaskConfig(
                            masking_character=config.DLP_MASK_CHARACTER,
                            number_to_mask=config.DLP_NUMBER_TO_MASK,
                        )
                    )
                )
            ]
        )
    )


def mask_pii(text: str, contract_id: str) -> tuple[str, list[str]]:
    if not config.DLP_ENABLED:
        log("DLP masking disabled -- skipping", severity="WARNING")
        return text, []

    client = dlp_v2.DlpServiceClient()
    parent = f"projects/{config.GCP_PROJECT_ID}/locations/{config.DLP_LOCATION}"
    item = dlp_v2.ContentItem(value=text)

    deidentify_request = dlp_v2.DeidentifyContentRequest(
        parent=parent,
        item=item,
        deidentify_config=_deidentify_config(),
        inspect_config=_inspect_config(),
        deidentify_template_name=config.DLP_DEIDENTIFY_TEMPLATE_NAME or None,
        inspect_template_name=config.DLP_INSPECT_TEMPLATE_NAME or None,
    )
    response = client.deidentify_content(request=deidentify_request)

    inspect_request = dlp_v2.InspectContentRequest(
        parent=parent,
        item=item,
        inspect_config=_inspect_config(),
        inspect_template_name=config.DLP_INSPECT_TEMPLATE_NAME or None,
    )
    inspect_response = client.inspect_content(request=inspect_request)
    detected_types = list({f.info_type.name for f in inspect_response.result.findings})

    log(
        "DLP masking complete",
        pii_types_detected=detected_types,
        findings_count=len(inspect_response.result.findings),
        using_templates=bool(config.DLP_INSPECT_TEMPLATE_NAME or config.DLP_DEIDENTIFY_TEMPLATE_NAME),
    )

    return response.item.value, detected_types
