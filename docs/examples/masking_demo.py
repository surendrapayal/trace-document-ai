"""
DLP Partial Masking Demo
========================
Simulates how Cloud DLP partial masking works — no GCP needed.

Run:
    python docs/examples/masking_demo.py
"""


class PartialMasker:
    """
    Masks a string value, keeping either the first N or last N characters visible.

    Args:
        mask_char       : character used to replace masked positions (default "*")
        show_last       : number of characters to keep visible at the END
        show_first      : number of characters to keep visible at the START
        chars_to_skip   : characters that are left in place and NOT counted
                          e.g. "-" in SSN so dashes don't eat into the visible count
    """

    def __init__(
        self,
        mask_char: str = "*",
        show_last: int = 0,
        show_first: int = 0,
        chars_to_skip: set[str] | None = None,
    ):
        self.mask_char = mask_char
        self.show_last = show_last
        self.show_first = show_first
        self.chars_to_skip = chars_to_skip or set()

    def mask(self, value: str) -> str:
        # Separate maskable characters from skipped ones (e.g. dashes, spaces)
        maskable = [c for c in value if c not in self.chars_to_skip]

        # Build a set of maskable-character positions to keep visible
        total = len(maskable)
        keep_indices: set[int] = set()

        if self.show_last:
            # Keep the last N maskable characters visible
            keep_indices.update(range(total - self.show_last, total))

        if self.show_first:
            # Keep the first N maskable characters visible
            keep_indices.update(range(self.show_first))

        # Walk the original string and mask/keep each character
        result = []
        maskable_pos = 0
        for char in value:
            if char in self.chars_to_skip:
                result.append(char)                # always keep skipped chars as-is
            else:
                if maskable_pos in keep_indices:
                    result.append(char)            # keep visible
                else:
                    result.append(self.mask_char)  # mask
                maskable_pos += 1

        return "".join(result)


# ── Per-type masking rules ────────────────────────────────────────────────────

MASKING_RULES = {
    # Numbers — show last 4, skip punctuation so dashes/spaces don't count
    "US_SOCIAL_SECURITY_NUMBER":  PartialMasker(show_last=4, chars_to_skip={"-"}),
    "US_BANK_ROUTING_MICR":       PartialMasker(show_last=4),
    "FINANCIAL_ACCOUNT_NUMBER":   PartialMasker(show_last=4),
    "PHONE_NUMBER":               PartialMasker(show_last=4, chars_to_skip={"(", ")", "-", " "}),
    "US_DRIVERS_LICENSE_NUMBER":  PartialMasker(show_last=4),

    # Email — show first 4
    "EMAIL_ADDRESS":              PartialMasker(show_first=4),

    # Sensitive — fully masked, replaced with label
    "PERSON_NAME":                None,   # → [PERSON_NAME]
    "DATE_OF_BIRTH":              None,   # → [DATE_OF_BIRTH]
    "STREET_ADDRESS":             None,   # → [STREET_ADDRESS]
}


def apply_masking(pii_type: str, value: str) -> str:
    """Apply the masking rule for the given PII type."""
    rule = MASKING_RULES.get(pii_type)
    if rule is None:
        return f"[{pii_type}]"   # fully masked with label
    return rule.mask(value)


# ── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    examples = [
        ("US_SOCIAL_SECURITY_NUMBER", "123-45-6789"),
        ("US_BANK_ROUTING_MICR",      "021000021"),
        ("FINANCIAL_ACCOUNT_NUMBER",  "1234567890"),
        ("PHONE_NUMBER",              "(555) 867-5309"),
        ("US_DRIVERS_LICENSE_NUMBER", "D1234567"),
        ("EMAIL_ADDRESS",             "john.smith@heartland.com"),
        ("PERSON_NAME",               "John Smith"),
        ("DATE_OF_BIRTH",             "01/15/1980"),
        ("STREET_ADDRESS",            "123 Main Street, Suite 400"),
    ]

    print(f"\n{'PII Type':<30} {'Original':<35} {'Masked'}")
    print("-" * 90)
    for pii_type, value in examples:
        masked = apply_masking(pii_type, value)
        print(f"{pii_type:<30} {value:<35} {masked}")
    print()
