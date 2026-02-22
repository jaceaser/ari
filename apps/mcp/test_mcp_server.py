#!/usr/bin/env python3
"""
MCP smoke test runner for ARI.

Usage:
  python3 test_mcp_server.py
  python3 test_mcp_server.py --base-url http://localhost:8100 --strict
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Callable
from urllib import error, request


def http_get_json(base_url: str, path: str, timeout: float) -> tuple[int, dict[str, Any] | None, str]:
    url = f"{base_url}{path}"
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = int(resp.status)
    except error.HTTPError as exc:
        return int(exc.code), None, exc.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return 0, None, str(exc)

    try:
        return status, json.loads(body), body
    except Exception:
        return status, None, body


def http_post_json(
    base_url: str, path: str, payload: dict[str, Any], timeout: float
) -> tuple[int, dict[str, Any] | None, str]:
    url = f"{base_url}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = int(resp.status)
    except error.HTTPError as exc:
        return int(exc.code), None, exc.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return 0, None, str(exc)

    try:
        return status, json.loads(body), body
    except Exception:
        return status, None, body


def build_test_cases(include_live: bool) -> list[dict[str, Any]]:
    # Prompts pulled from your "ARI - Example Prompts.pdf" categories plus route checks.
    cases: list[dict[str, Any]] = [
        {
            "name": "extract_city_state",
            "path": "/tools/extract-city-state",
            "payload": {"prompt": "Show me cash buyers in Houston, TX."},
            "allow_error_status": False,
            "expected_tool": "extract-city-state",
            "checks": [
                {"path": "result.city", "contains": "Houston"},
                {"path": "result.state", "equals": "TX"},
                {"path": "result.location_source", "in": ["prompt", "arguments"]},
            ],
        },
        {
            "name": "extract_address",
            "path": "/tools/extract-address",
            "payload": {"prompt": "Run comps for 123 Main St, Dallas, TX 75201."},
            "allow_error_status": False,
            "expected_tool": "extract-address",
            "checks": [
                {"path": "result.address", "contains": "123 Main St"},
                {"path": "result.address", "contains": "TX 75201"},
                {"path": "result.address_candidates", "type": "list"},
            ],
        },
        {
            "name": "classify_wholesaling",
            "path": "/tools/classify",
            "payload": {"prompt": "What is wholesaling in real estate and how does it work?"},
            "allow_error_status": False,
            "expected_tool": "classify",
            "checks": [
                {"path": "result.route", "equals": "Education"},
                {"path": "result.scores", "type": "dict"},
            ],
        },
        {
            "name": "education_sub2",
            "path": "/tools/education",
            "payload": {
                "prompt": "What does Subject To the existing mortgage mean in real estate?"
            },
            "allow_error_status": False,
            "expected_tool": "education",
            "checks": [
                {"path": "result.route", "equals": "Education"},
                {"path": "result.retrieval_query", "contains": "subject"},
                {"path": "result.subtopics", "type": "list"},
            ],
        },
        {
            "name": "education_fix_flip",
            "path": "/tools/education",
            "payload": {"prompt": "What is the 70% rule and how does it apply to flipping?"},
            "allow_error_status": False,
            "expected_tool": "education",
            "checks": [
                {"path": "result.route", "equals": "Education"},
                {"path": "result.retrieval_query", "contains": "rule"},
            ],
        },
        {
            "name": "strategy_plan",
            "path": "/tools/strategy",
            "payload": {
                "prompt": "Build me a 90-day plan to close my first wholesale and Sub2 deal."
            },
            "allow_error_status": False,
            "expected_tool": "strategy",
            "checks": [
                {"path": "result.route", "equals": "Strategy"},
                {"path": "result.retrieval_query", "contains": "plan"},
            ],
        },
        {
            "name": "contracts_assignment",
            "path": "/tools/contracts",
            "payload": {
                "prompt": "What key clauses should I include in a wholesale assignment contract in Texas?"
            },
            "allow_error_status": False,
            "expected_tool": "contracts",
            "checks": [
                {"path": "result.route", "equals": "Contracts"},
                {"path": "result.expanded_prompt", "contains": "key clauses"},
                {"path": "result.contracts_expansion_prompt", "type": "str"},
            ],
        },
        {
            "name": "attorneys_probate",
            "path": "/tools/attorneys",
            "payload": {"prompt": "Find probate attorneys in Phoenix, AZ for investor work."},
            "allow_error_status": False,
            "expected_tool": "attorneys",
            "checks": [
                {"path": "result.route", "equals": "Attorneys"},
                {"path": "result.state", "equals": "AZ"},
                {"path": "result.city", "contains": "Phoenix"},
            ],
        },
        {
            "name": "leads_link_type",
            "path": "/tools/infer-lead-type",
            "payload": {
                "prompt": 'Classify this lead URL: https://www.zillow.com/homes/for_sale/?searchQueryState={"pf":{"value":true}}'
            },
            "allow_error_status": False,
            "expected_tool": "infer-lead-type",
            "checks": [
                {"path": "result.lead_type", "equals": "Pre-Foreclosure"},
                {"path": "result.url", "contains": "zillow.com"},
            ],
        },
        {
            "name": "retrieval_query_builder",
            "path": "/tools/build-retrieval-query",
            "payload": {
                "prompt": "How do I calculate ARV and run comps in Dallas TX for a wholesale deal?"
            },
            "allow_error_status": False,
            "expected_tool": "build-retrieval-query",
            "checks": [
                {"path": "result.retrieval_query", "contains": "arv"},
                {"path": "result.retrieval_query", "contains": "dallas"},
            ],
        },
    ]

    if include_live:
        cases.extend(
            [
                {
                    "name": "buyers_search_houston",
                    "path": "/tools/buyers-search",
                    "payload": {
                        "prompt": "Show me cash buyers in Houston, TX.",
                        "arguments": {"city": "Houston", "state": "TX", "max_results": 10},
                    },
                    "allow_error_status": True,
                    "expected_tool": "buyers-search",
                    "checks": [
                        {"path": "result.route", "equals": "Buyers"},
                        {"path": "result.state", "equals": "TX"},
                        {"path": "result.city", "contains": "Houston"},
                        {"path": "result.data_source", "equals": "cosmos"},
                        {"path": "result.buyers_preview", "type": "list"},
                        {"path": "result.status", "in": ["ok", "no_results", "error"]},
                    ],
                    "validator": "validate_buyers_live",
                },
                {
                    "name": "buyers_route_los_angeles",
                    "path": "/tools/buyers",
                    "payload": {
                        "prompt": "Can I get a list of real estate buyers in Los Angeles, CA?"
                    },
                    "allow_error_status": True,
                    "expected_tool": "buyers",
                    "checks": [
                        {"path": "result.route", "equals": "Buyers"},
                        {"path": "result.state", "equals": "CA"},
                        {"path": "result.city", "contains": "Los Angeles"},
                        {"path": "result.data_source", "equals": "cosmos"},
                        {"path": "result.status", "in": ["ok", "no_results", "error"]},
                    ],
                    "validator": "validate_buyers_live",
                },
                {
                    "name": "bricked_comps",
                    "path": "/tools/bricked-comps",
                    "payload": {
                        "prompt": "Run comps for 123 Main St, Dallas, TX 75201.",
                        "arguments": {"address": "123 Main St, Dallas, TX 75201", "max_comps": 6},
                    },
                    "allow_error_status": True,
                    "expected_tool": "bricked-comps",
                    "checks": [
                        {"path": "result.route", "equals": "Comps"},
                        {"path": "result.subject_address", "contains": "123 Main St"},
                        {"path": "result.data_source", "equals": "bricked"},
                        {"path": "result.status", "in": ["ok", "error", "missing_address"]},
                    ],
                    "validator": "validate_comps_live",
                },
                {
                    "name": "comps_route",
                    "path": "/tools/comps",
                    "payload": {"prompt": "Estimate ARV for 123 Main St, Dallas, TX 75201."},
                    "allow_error_status": True,
                    "expected_tool": "comps",
                    "checks": [
                        {"path": "result.route", "equals": "Comps"},
                        {"path": "result.data_source", "equals": "bricked"},
                        {"path": "result.status", "in": ["ok", "error", "missing_address"]},
                    ],
                    "validator": "validate_comps_live",
                },
            ]
        )

    return cases


def _shorten(text: str, max_len: int = 220) -> str:
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}..."


def _get_path_value(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for token in path.split("."):
        if isinstance(current, dict) and token in current:
            current = current[token]
            continue
        return None
    return current


def _matches_type(value: Any, expected_type: str) -> bool:
    mapping: dict[str, type] = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "dict": dict,
        "list": list,
    }
    py_type = mapping.get(expected_type)
    if py_type is None:
        return False
    return isinstance(value, py_type)


def _run_case_checks(case: dict[str, Any], data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_tool = case.get("expected_tool")
    if expected_tool and data.get("tool") != expected_tool:
        errors.append(f"tool expected '{expected_tool}' got '{data.get('tool')}'")

    checks = case.get("checks", [])
    for check in checks:
        path = check["path"]
        value = _get_path_value(data, path)

        if value is None:
            errors.append(f"missing path '{path}'")
            continue

        if "type" in check and not _matches_type(value, check["type"]):
            errors.append(f"path '{path}' expected type={check['type']} got={type(value).__name__}")

        if "equals" in check and value != check["equals"]:
            errors.append(f"path '{path}' expected '{check['equals']}' got '{value}'")

        if "contains" in check:
            needle = str(check["contains"])
            haystack = str(value)
            if needle.lower() not in haystack.lower():
                errors.append(f"path '{path}' expected to contain '{needle}' got '{haystack}'")

        if "in" in check and value not in check["in"]:
            errors.append(f"path '{path}' expected one of {check['in']} got '{value}'")

    return errors


def validate_buyers_live(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    result = data.get("result")
    if not isinstance(result, dict):
        return ["result is not an object"]

    status = result.get("status")
    if status == "ok":
        if not isinstance(result.get("buyers_preview"), list):
            errors.append("buyers_preview should be list when status=ok")
        if not isinstance(result.get("buyers_count"), int):
            errors.append("buyers_count should be int when status=ok")
    elif status in {"no_results", "error"}:
        if not isinstance(result.get("message"), str) or not result.get("message"):
            errors.append("message should be non-empty string for no_results/error")
    return errors


def validate_comps_live(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    result = data.get("result")
    if not isinstance(result, dict):
        return ["result is not an object"]

    status = result.get("status")
    if status == "ok":
        bricked = result.get("bricked")
        if not isinstance(bricked, dict):
            errors.append("bricked should be object when status=ok")
        else:
            for key in ["subject", "arv", "cmv", "comps"]:
                if key not in bricked:
                    errors.append(f"bricked missing key '{key}'")
    elif status in {"error", "missing_address"}:
        if not isinstance(result.get("message"), str) or not result.get("message"):
            errors.append("message should be non-empty string for error/missing_address")
    return errors


VALIDATORS: dict[str, Callable[[dict[str, Any]], list[str]]] = {
    "validate_buyers_live": validate_buyers_live,
    "validate_comps_live": validate_comps_live,
}


def summarize_result(data: dict[str, Any] | None) -> str:
    if not isinstance(data, dict):
        return "invalid-json"

    if "error" in data and not data.get("ok", True):
        return str(data.get("error"))

    result = data.get("result", {})
    if not isinstance(result, dict):
        return "ok"

    if "route" in result:
        return f"route={result.get('route')}"
    if "status" in result:
        return f"status={result.get('status')}"
    if "city" in result or "state" in result:
        return f"city={result.get('city')} state={result.get('state')}"
    if "address" in result:
        return f"address={result.get('address')}"
    return "ok"


def run(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    timeout = float(args.timeout)

    print(f"Testing MCP server at {base_url}")
    print("-" * 72)

    hard_failures = 0
    soft_warnings = 0
    assertion_failures = 0
    total = 0

    health_status, health_data, health_raw = http_get_json(base_url, "/health", timeout)
    total += 1
    if health_status != 200 or not isinstance(health_data, dict):
        hard_failures += 1
        print(f"[FAIL] GET /health -> {health_status} :: {health_raw[:220]}")
    else:
        print(f"[PASS] GET /health -> {health_status} :: status={health_data.get('status')}")

    tools_status, tools_data, tools_raw = http_get_json(base_url, "/tools", timeout)
    total += 1
    if tools_status != 200 or not isinstance(tools_data, dict):
        hard_failures += 1
        print(f"[FAIL] GET /tools -> {tools_status} :: {tools_raw[:220]}")
    else:
        tool_count = len(tools_data.get("tools", [])) if isinstance(tools_data.get("tools"), list) else 0
        print(f"[PASS] GET /tools -> {tools_status} :: tools={tool_count}")

    cases = build_test_cases(include_live=not args.skip_live)
    print("-" * 72)
    print(
        f"Running {len(cases)} prompt tests (live checks {'off' if args.skip_live else 'on'}, "
        f"assertions {'on' if not args.skip_assertions else 'off'})"
    )

    for case in cases:
        total += 1
        start = time.time()
        status_code, data, raw = http_post_json(base_url, case["path"], case["payload"], timeout)
        elapsed_ms = int((time.time() - start) * 1000)

        if status_code != 200:
            hard_failures += 1
            print(
                f"[FAIL] {case['name']} {case['path']} -> {status_code} ({elapsed_ms}ms) :: {raw[:220]}"
            )
            continue

        if not isinstance(data, dict) or data.get("ok") is not True:
            hard_failures += 1
            print(
                f"[FAIL] {case['name']} {case['path']} -> malformed body ({elapsed_ms}ms) :: {raw[:220]}"
            )
            continue

        result = data.get("result")
        status_hint = result.get("status") if isinstance(result, dict) else None

        if status_hint == "error" and case.get("allow_error_status", False):
            soft_warnings += 1
            print(
                f"[WARN] {case['name']} {case['path']} -> 200 ({elapsed_ms}ms) :: {summarize_result(data)}"
            )
            if args.skip_assertions:
                continue

        if status_hint == "error":
            hard_failures += 1
            print(
                f"[FAIL] {case['name']} {case['path']} -> status=error ({elapsed_ms}ms) :: {summarize_result(data)}"
            )
            continue

        assertion_errors: list[str] = []
        if not args.skip_assertions:
            assertion_errors.extend(_run_case_checks(case, data))

            validator_name = case.get("validator")
            if validator_name:
                validator = VALIDATORS.get(validator_name)
                if validator is None:
                    assertion_errors.append(f"unknown validator '{validator_name}'")
                else:
                    assertion_errors.extend(validator(data))

        if assertion_errors:
            assertion_failures += 1
            reason = _shorten("; ".join(assertion_errors), 260)
            print(
                f"[FAIL] {case['name']} {case['path']} -> assertion failure ({elapsed_ms}ms) :: {reason}"
            )
            if args.show_fail_json:
                print(_shorten(json.dumps(data, ensure_ascii=False), 1200))
            continue

        print(
            f"[PASS] {case['name']} {case['path']} -> {status_code} ({elapsed_ms}ms) :: {summarize_result(data)}"
        )

    print("-" * 72)
    print(
        f"Summary: total={total} passed={total - hard_failures - soft_warnings - assertion_failures} "
        f"warnings={soft_warnings} failed={hard_failures} assertion_failures={assertion_failures}"
    )

    if hard_failures > 0 or assertion_failures > 0:
        return 1
    if args.strict and soft_warnings > 0:
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test ARI MCP tool server endpoints.")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8100",
        help="MCP base URL (default: http://localhost:8100)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=45.0,
        help="Per-request timeout in seconds (default: 45)",
    )
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help="Skip live external checks (Cosmos buyers + Bricked comps).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings (e.g. live status=error) as failures.",
    )
    parser.add_argument(
        "--skip-assertions",
        action="store_true",
        help="Run only smoke checks (skip endpoint-specific assertions).",
    )
    parser.add_argument(
        "--show-fail-json",
        action="store_true",
        help="Print response JSON snippet when assertions fail.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(run(parse_args()))
