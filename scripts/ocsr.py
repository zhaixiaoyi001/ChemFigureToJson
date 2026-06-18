#!/usr/bin/env python
"""Recognize a PNG chemical structure image with the MolParser OCSR API."""

from __future__ import annotations

import argparse
import base64
import sys
import time
from pathlib import Path
from typing import Any

import requests


API_URL = "https://ocsr.dp.tech/mol/img2mol"
REQUEST_INTERVAL_SECONDS = 2.0

CHROME_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": "https://ocsr.dp.tech",
    "Referer": "https://ocsr.dp.tech/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/98.0.4758.82 Safari/537.36"
    ),
    "Sec-Ch-Ua": '"(Not(A:Brand";v="8", "Chromium";v="98"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


class OCSRError(RuntimeError):
    """Raised when OCSR recognition fails."""


def _image_to_base64(path: Path) -> str:
    if not path.exists():
        raise OCSRError(f"file not found: {path}")
    if not path.is_file():
        raise OCSRError(f"not a file: {path}")
    if path.suffix.lower() != ".png":
        raise OCSRError("input file must be a PNG")

    return base64.b64encode(path.read_bytes()).decode("ascii")


def _parse_ocsr_result(response_json: dict[str, Any]) -> str:
    if response_json.get("code") != 0:
        msg = response_json.get("msg") or "OCSR API returned a non-zero code"
        raise OCSRError(str(msg))

    data = response_json.get("data")
    if not isinstance(data, str) or not data:
        raise OCSRError("OCSR API response did not contain a SMILES string")

    return data


def recognize_png(path: str, timeout: float = 60.0) -> str:
    """Return the OCSR string recognized from a local PNG file."""

    image_path = Path(path)
    payload = {"base64_img": _image_to_base64(image_path)}

    time.sleep(REQUEST_INTERVAL_SECONDS)
    try:
        response = requests.post(
            API_URL,
            json=payload,
            headers=CHROME_HEADERS,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise OCSRError(f"request failed: {exc}") from exc

    try:
        response_json = response.json()
    except ValueError as exc:
        raise OCSRError("OCSR API response was not valid JSON") from exc

    if not isinstance(response_json, dict):
        raise OCSRError("OCSR API response JSON was not an object")

    return _parse_ocsr_result(response_json)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recognize a PNG chemical structure image as SMILES."
    )
    parser.add_argument("png_path", help="Path to a local PNG image.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        smiles = recognize_png(args.png_path)
    except OCSRError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(smiles)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
