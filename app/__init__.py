# coding: latin-1
###############################################################################
# Copyright (c) 2023 European Commission
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
###############################################################################
"""
The PID Issuer Web service is a component of the PID Provider backend.
Its main goal is to issue the PID in cbor/mdoc (ISO 18013-5 mdoc) and SD-JWT format.

This __init__.py serves double duty: it will contain the application factory,
and it tells Python that the flask directory should be treated as a package.
"""

import logging
import os
import sys

sys.path.append(os.path.dirname(__file__))

from urllib.parse import urlparse

from app_config.config_service import ConfService as cfgserv
from app_config.oid_config import build_oid_config
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
from flask import Flask, render_template, send_from_directory
from flask_cors import CORS
from flask_session import Session
from idpyoidc.configure import Configuration
from idpyoidc.server import Server
from idpyoidc.server.configure import OPConfiguration
from pycose.keys import EC2Key

# from werkzeug.debug import *
from werkzeug.exceptions import HTTPException

# Log
from .metadata_config import build_metadata

oidc_metadata = {}
openid_metadata = {}
oauth_metadata = {}
trusted_CAs = {}


def setup_metadata():
    global oidc_metadata
    global openid_metadata
    global oauth_metadata

    oidc_metadata, openid_metadata, oauth_metadata = build_metadata(cfgserv)


def setup_trusted_CAs():
    global trusted_CAs
    logger = cfgserv.app_logger.getChild("trusted_ca_loader")

    ec_keys = {}
    for file in os.listdir(cfgserv.trusted_CAs_path):
        if not file.endswith("pem"):
            continue

        try:
            CA_path = os.path.join(cfgserv.trusted_CAs_path, file)

            logger.debug(f"Loading CA: {CA_path}")
            with open(CA_path) as pem_file:
                pem_data = pem_file.read()

                pem_data = pem_data.encode()

                certificate = x509.load_pem_x509_certificate(
                    pem_data, default_backend()
                )

                public_key = certificate.public_key()

                if not isinstance(public_key, ec.EllipticCurvePublicKey):
                    raise ValueError(
                        f"CA certicate {CA_path} is not using elliptic curve"
                    )

                issuer = certificate.issuer

                not_valid_before = certificate.not_valid_before

                not_valid_after = certificate.not_valid_after

                x = public_key.public_numbers().x.to_bytes(
                    (public_key.public_numbers().x.bit_length() + 7)
                    // 8,  # Number of bytes needed
                    "big",  # Byte order
                )

                y = public_key.public_numbers().y.to_bytes(
                    (public_key.public_numbers().y.bit_length() + 7)
                    // 8,  # Number of bytes needed
                    "big",  # Byte order
                )

                ec_key = EC2Key(
                    x=x, y=y, crv=1
                )  # SECP256R1 curve is equivalent to P-256

                ec_keys.update(
                    {
                        issuer: {
                            "certificate": certificate,
                            "public_key": public_key,
                            "not_valid_before": not_valid_before,
                            "not_valid_after": not_valid_after,
                            "ec_key": ec_key,
                        }
                    }
                )

        except FileNotFoundError as e:
            cfgserv.app_logger.exception(f"TrustedCA Error: file not found. {file} {e}")
        except Exception as e:
            cfgserv.app_logger.exception(
                f"TrustedCA Error: An unexpected error occurred. {file} {e}"
            )

    trusted_CAs = ec_keys


def handle_exception(e: Exception):
    # pass through HTTP errors
    if isinstance(e, HTTPException):
        return e
    cfgserv.app_logger.error("- WARN - Error 500", e)
    # now you're handling non-HTTP exceptions only
    return (
        render_template(
            "misc/500.html",
            error="Sorry, an internal server error has occurred. Our team has been notified and is working to resolve the issue. Please try again later.",
            error_code="Internal Server Error",
        ),
        500,
    )


def page_not_found(e: Exception):
    cfgserv.app_logger.exception("- WARN - Error 404", e)
    return (
        render_template(
            "misc/500.html",
            error_code="Page not found",
            error="Page not found. We're sorry, we couldn't find the page you requested.",
        ),
        404,
    )


def create_app(test_config=None):
    setup_metadata()
    setup_trusted_CAs()

    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)

    app.register_error_handler(Exception, handle_exception)
    app.register_error_handler(404, page_not_found)
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)

    @app.route("/", methods=["GET"])
    def initial_page():
        return render_template(
            "misc/initial_page.html", oidc=cfgserv.oidc, service_url=cfgserv.service_url
        )

    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory("static/images", "favicon.ico")

    @app.route("/ic-logo.png")
    def logo():
        return send_from_directory("static/images", "ic-logo.png")

    app.config.from_mapping(SECRET_KEY="dev")

    if test_config is None:
        # load the instance config (in instance directory), if it exists, when not testing
        app.config.from_pyfile("config.py", silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # a simple page that says hello
    # @app.route('/hello')
    # def hello():
    #    return 'Hello, World!'

    # register blueprint for the /pid route
    from . import (
        preauthorization,
        route_dynamic,
        route_eidasnode,
        route_formatter,
        route_oid4vp,
        route_oidc,
    )
    from .test_cases import lt as lt_testcases

    app.register_blueprint(route_eidasnode.eidasnode)
    app.register_blueprint(route_formatter.formatter)
    app.register_blueprint(route_oidc.oidc)
    app.register_blueprint(route_oid4vp.oid4vp)
    app.register_blueprint(route_dynamic.dynamic)
    app.register_blueprint(preauthorization.preauth)
    app.register_blueprint(lt_testcases.mdl.blueprint)
    app.register_blueprint(lt_testcases.pid.blueprint)

    # config session
    app.config["SESSION_FILE_THRESHOLD"] = 50
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_TYPE"] = "filesystem"
    app.config.update(SESSION_COOKIE_SAMESITE="None", SESSION_COOKIE_SECURE=True)
    Session(app)

    # CORS is a mechanism implemented by browsers to block requests
    # from domains other than the server's one.
    CORS(app, supports_credentials=True)

    cfgserv.app_logger.info(" - DEBUG - FLASK started")

    dir_path = os.path.dirname(os.path.realpath(__file__))

    config = Configuration(
        build_oid_config(cfgserv),
        entity_conf=[
            {"class": OPConfiguration, "attr": "op", "path": ["op", "server_info"]}
        ],
        base_path=dir_path,
    )
    config.logger = cfgserv.app_logger.getChild("oidc")
    app.srv_config = config.op

    server = Server(config.op, cwd=dir_path)

    for endp in server.endpoint.values():
        p = urlparse(endp.endpoint_path)
        _vpath = p.path.split("/")
        if _vpath[0] == "":
            endp.vpath = _vpath[1:]
        else:
            endp.vpath = _vpath

    app.server = server

    return app


#
# Usage examples:
# flask --app app run --debug
# flask --app app run --debug --cert=app/certs/certHttps.pem --key=app/certs/PID-DS-0001_UT.pem --host=127.0.0.1 --port=4430
#
