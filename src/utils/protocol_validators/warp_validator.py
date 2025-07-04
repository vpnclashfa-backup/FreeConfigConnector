from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, parse_qs, unquote, quote

class WarpValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not link.startswith("warp://"):
            return False
        try:
            parsed_url = urlparse(link)
            # Warp links are often simple, sometimes just "warp://".
            # More complex ones might have a UUID for WARP+ or a specific parameter for teams.
            
            # If there's a netloc, it could be a UUID or an endpoint.
            if parsed_url.netloc:
                if not BaseValidator._is_valid_uuid(parsed_url.netloc) and \
                   not BaseValidator._is_valid_domain(parsed_url.netloc) and \
                   not BaseValidator._is_valid_ipv4(parsed_url.netloc) and \
                   not BaseValidator._is_valid_ipv6(parsed_url.netloc):
                    # It could be a simple "warp://" or something else we don't validate strictly
                    pass 
            
            # Check for common query parameters like 'name', 'orgid', 'license'
            query_params = parse_qs(parsed_url.query)
            # If 'orgid' or 'license' is present, it usually indicates a Team Warp or WARP+ config.
            # No strict validation needed for now, just checking existence of prefix.
            
            return True
        except Exception:
            return False

    @staticmethod
    def clean(link: str) -> str:
        cleaned_link = link.strip()
        parts = cleaned_link.split('#', 1)
        if len(parts) > 1:
            main_part = parts[0]
            tag_part = unquote(parts[1])
            tag_part = tag_part.strip().replace(' ', '_')
            cleaned_link = f"{main_part}#{quote(tag_part)}"
        return cleaned_link