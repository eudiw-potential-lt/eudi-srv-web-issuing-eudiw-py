import os
import json
from urllib.parse import urljoin, urlparse

from ..app_config.config_service import ConfService

from .openid_configuration import build_openid_configuration


def build_metadata(cfgserv: ConfService):
    oidc_metadata = {
        # This is hacky as hell, but wallet really does not do proper URL validation.
        "credential_issuer": urlparse(cfgserv.service_url)
        ._replace(path=urlparse(cfgserv.service_url).path.removesuffix("/"))
        .geturl(),
        "credential_endpoint": urljoin(cfgserv.service_url, "credential"),
        "batch_credential_endpoint": urljoin(cfgserv.service_url, "batch_credential"),
        "notification_endpoint": urljoin(cfgserv.service_url, "notification"),
        "deferred_credential_endpoint": urljoin(
            cfgserv.service_url, "deferred_credential"
        ),
        "display": [
            {
                "name": cfgserv.pid_organization_id,
                "locale": "en",
                "logo": {
                    "uri": urljoin(cfgserv.service_url, "ic-logo.png"),
                    "alt_text": "EU Digital Identity Wallet Logo",
                },
            }
        ],
        "credential_configurations_supported": {},
    }
    oauth_metadata = {
        "issuer": urlparse(cfgserv.service_url)
        ._replace(path=urlparse(cfgserv.service_url).path.removesuffix("/"))
        .geturl(),
        "authorization_endpoint": urljoin(cfgserv.service_url, "authorizationV3"),
        "token_endpoint": urljoin(cfgserv.service_url, "token"),
        "token_endpoint_auth_methods_supported": ["public"],
        "token_endpoint_auth_signing_alg_values_supported": ["ES256"],
        "code_challenge_methods_supported": ["S256"],
        "userinfo_endpoint": urljoin(cfgserv.service_url, "userinfo"),
        "jwks_uri": urljoin(cfgserv.service_url, "static/jwks.json"),
        "registration_endpoint": urljoin(cfgserv.service_url, "registration"),
        "scopes_supported": ["openid"],
        "response_types_supported": ["code"],
    }

    openid_metadata = build_openid_configuration(cfgserv)

    credentials_supported = {}

    dir_path = os.path.dirname(os.path.realpath(__file__))

    for file in os.listdir(os.path.join(dir_path, "credentials_supported")):
        if not file.endswith("json"):
            continue

        json_path = os.path.join(dir_path, "credentials_supported", file)
        try:
            with open(json_path, encoding="utf-8") as json_file:
                credential = json.load(json_file)
                credentials_supported.update(credential)

        except FileNotFoundError as e:
            cfgserv.app_logger.exception(
                "Metadata Error: file not found. %s - %s", json_path, e
            )
        except json.JSONDecodeError as e:
            cfgserv.app_logger.exception(
                "Metadata Error: Metadata Unable to decode JSON. %s - %s", json_path, e
            )
        except Exception as e:
            cfgserv.app_logger.exception(
                "Metadata Error: An unexpected error occurred. %s -  %s", json_path, e
            )

    oidc_metadata["credential_configurations_supported"] = credentials_supported

    return oidc_metadata, openid_metadata, oauth_metadata
