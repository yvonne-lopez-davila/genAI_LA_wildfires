"""
Run system-level evaluation for the wildfire report API with an LLM-as-judge rubric.

Usage:
    python3 py/wildfireRisk/eval/run_report_eval.py

Start the app separately first, for example:
    cd py/wildfireRisk
    uvicorn backend.app:app --reload

The runner loads 10 representative homeowner/buyer cases, calls /analyzeFireRisk,
keeps lightweight automated guardrail checks, then asks an LLM judge to grade:
role fit, data grounding, specificity, RAG retrieval relevance, RAG grounding
faithfulness, source relevance, confidence calibration, safety/no hallucination,
overall pass/fail, and notes.

It saves raw API responses, automated checks, and judge scores under:
    py/wildfireRisk/eval/results/

You can also judge an existing result file without rerunning the API:
    python3 py/wildfireRisk/eval/run_report_eval.py --score-existing <result.json>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
PY_DIR = BASE_DIR.parents[1]
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from llmproxy import LLMProxy

load_dotenv()

CASES_PATH = BASE_DIR / "report_eval_cases.json"
RESULTS_DIR = BASE_DIR / "results"

REQUIRED_FIELDS = {
    "home_value_impact",
    "insurance_outlook",
    "affordability_score",
    "confidence",
    "confidence_explanation",
    "hazard_zone",
    "trends",
    "fair_plan",
    "doi",
}

BUYER_FORBIDDEN_CONFIDENCE_TERMS = {
    "roof",
    "eaves",
    "siding",
    "dins",
    "structural",
    "homeowner-provided",
    "property characteristics",
}

HOMEOWNER_ACTION_TERMS = {
    "defensible",
    "home hardening",
    "roof",
    "vents",
    "eaves",
    "siding",
    "ember",
    "mitigation",
}


RUBRIC_FIELDS = (
    "role_fit",
    "data_grounding",
    "specificity",
    "rag_retrieval_relevance",
    "rag_grounding_faithfulness",
    "rag_source_relevance",
    "confidence_calibration",
    "safety_no_hallucination",
)

JUDGE_SYSTEM_PROMPT = """
You are an evaluator for a California wildfire risk report system.
Score the report strictly using the rubric below. Return only valid JSON.

Scoring scale:
1 = poor / major failure
2 = weak / several issues
3 = acceptable but imperfect
4 = good
5 = excellent

Rubric fields:
- role_fit: Does the report match the requested user role? Homeowner should emphasize current ownership and mitigation/action. Buyer should emphasize purchase decision, comparison, value, insurance access, and affordability.
- data_grounding: Does the report correctly use available structured data such as hazard zone, fire history, Zillow value data, FAIR Plan data, DOI non-renewal data, and DINS where appropriate?
- specificity: Is the report concrete, specific, and useful rather than generic?
- rag_retrieval_relevance: Do the retrieved RAG snippets/chunks match the case, user role, and report query? Penalize irrelevant, off-topic, or overly generic retrieval.
- rag_grounding_faithfulness: Are RAG-backed claims in the generated report supported by the retrieved snippets? Penalize invented mitigation guidance, insurance claims, or source claims not present in retrieved context or structured data.
- rag_source_relevance: Are cited/referenced external guidance or RAG-style sources relevant to the report and user role? If no explicit citations are present, judge whether source-derived content appears appropriate and whether retrieved sources would have supported better citation.
- confidence_calibration: Is the confidence category and confidence explanation consistent with the amount and specificity of available data?
- safety_no_hallucination: Does the report avoid unsupported facts, malformed links, invented property details, unsupported insurer claims, and role-inappropriate data leakage?
- overall_pass: true only if the report is acceptable for that user role with no major safety, hallucination, or role-fit failures.
- notes: One concise sentence explaining the main reason for the scores.

Important:
- Buyer reports should not provide mitigation recommendations or rely on homeowner structural characteristics unless explicitly provided in the buyer case.
- Homeowner reports may use DINS/property characteristics and mitigation guidance when available.
- Penalize confident claims that are not supported by the provided response data.
- If rag_context is present, evaluate retrieval quality separately from whether the final report used it well.
- If rag_context is missing or contains an error, give rag_retrieval_relevance and rag_grounding_faithfulness low scores unless the report correctly avoids RAG-dependent claims.

Return exactly this JSON object:
{
  "role_fit": 1-5,
  "data_grounding": 1-5,
  "specificity": 1-5,
  "rag_retrieval_relevance": 1-5,
  "rag_grounding_faithfulness": 1-5,
  "rag_source_relevance": 1-5,
  "confidence_calibration": 1-5,
  "safety_no_hallucination": 1-5,
  "overall_pass": true or false,
  "notes": "..."
}
"""


def load_cases(path: Path) -> List[Dict[str, Any]]:
    return json.loads(path.read_text())


def call_api(base_url: str, case: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    payload = {
        "lat": case["lat"],
        "lon": case["lon"],
        "zipcode": case.get("zipcode"),
        "user_type": case["user_type"],
        "property_chars": case.get("property_chars"),
    }
    response = requests.post(
        f"{base_url.rstrip('/')}/analyzeFireRisk",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def one_sentence_ish(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return False
    sentence_marks = sum(text.count(mark) for mark in ".!?")
    return sentence_marks <= 2 and len(text.split()) <= 45


def check_case(case: Dict[str, Any], data: Dict[str, Any]) -> List[Tuple[bool, str]]:
    checks: List[Tuple[bool, str]] = []
    missing = sorted(field for field in REQUIRED_FIELDS if field not in data)
    checks.append((not missing, f"required fields present ({', '.join(missing) or 'none missing'})"))

    confidence = str(data.get("confidence", "")).lower()
    checks.append((confidence in {"high", "medium", "low"}, f"confidence category valid ({confidence or 'missing'})"))

    explanation = str(data.get("confidence_explanation", ""))
    checks.append((one_sentence_ish(explanation), "confidence explanation is present and short"))

    for field in ("home_value_impact", "insurance_outlook", "affordability_score"):
        checks.append((bool(str(data.get(field, "")).strip()), f"{field} is non-empty"))

    rag_context = data.get("rag_context")
    rag_available = rag_context is not None and not (isinstance(rag_context, dict) and "error" in rag_context)
    checks.append((rag_available, "RAG retrieved context is available for evaluation"))

    trends = data.get("trends") or {}
    signals = ((trends.get("composite") or {}).get("signals") or [])
    checks.append((len(signals) >= 3, f"at least 3 risk signals available ({len(signals)})"))

    if case["user_type"] == "buyer":
        mitigation = data.get("mitigation_recommendations")
        checks.append((mitigation in (None, "", "null"), "buyer has no mitigation recommendations"))

        lower_expl = explanation.lower()
        leaked = sorted(term for term in BUYER_FORBIDDEN_CONFIDENCE_TERMS if term in lower_expl)
        checks.append((not leaked, f"buyer confidence avoids homeowner/DINS leakage ({', '.join(leaked) or 'none'})"))

        buyer_text = " ".join(
            str(data.get(field, "")) for field in ("home_value_impact", "insurance_outlook", "affordability_score")
        ).lower()
        checks.append((any(term in buyer_text for term in ("buy", "buyer", "purchase", "private insurance", "fair plan")),
                       "buyer report uses purchase/insurance framing"))
    else:
        mitigation = str(data.get("mitigation_recommendations") or "")
        if mitigation and mitigation != "INSUFFICIENT_DATA":
            lower_mitigation = mitigation.lower()
            checks.append((any(term in lower_mitigation for term in HOMEOWNER_ACTION_TERMS),
                           "homeowner mitigation contains action-specific language"))
        else:
            checks.append((True, "homeowner mitigation absent/insufficient-data allowed for low-data cases"))

        homeowner_text = " ".join(
            str(data.get(field, "")) for field in ("home_value_impact", "insurance_outlook", "affordability_score")
        ).lower()
        checks.append(("should they buy" not in homeowner_text and "purchase decision" not in homeowner_text,
                       "homeowner report avoids buyer framing"))

    return checks


def clamp_score(score: int) -> int:
    return max(1, min(5, score))


def contains_any(text: str, terms: set[str] | tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def truncate_text(value: Any, limit: int = 900) -> Any:
    if not isinstance(value, str):
        return value
    compact = re.sub(r"\s+", " ", value).strip()
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "..."


def compact_rag_context(rag_context: Any) -> Any:
    if rag_context is None:
        return None
    if isinstance(rag_context, dict) and "error" in rag_context:
        return rag_context
    if not isinstance(rag_context, list):
        return truncate_text(rag_context)

    compact = []
    for collection in rag_context[:5]:
        if not isinstance(collection, dict):
            compact.append(truncate_text(collection))
            continue

        chunks = collection.get("chunks") or []
        compact.append(
            {
                "doc_summary": truncate_text(collection.get("doc_summary"), 500),
                "chunks": [truncate_text(chunk, 700) for chunk in chunks[:4]],
            }
        )
    return compact


def judge_query(case: Dict[str, Any], data: Dict[str, Any], checks: List[Tuple[bool, str]]) -> str:
    compact_response = {
        key: data.get(key)
        for key in (
            "home_value_impact",
            "insurance_outlook",
            "affordability_score",
            "mitigation_recommendations",
            "confidence",
            "confidence_explanation",
            "hazard_zone",
            "hazard_lookup_error",
            "source_layer",
            "zhvi",
            "fair_plan",
            "doi",
            "fire_history",
            "trends",
            "dins",
        )
        if key in data
    }
    rag_context = compact_rag_context(data.get("rag_context"))
    check_summary = [{"passed": ok, "check": label} for ok, label in checks]
    return json.dumps(
        {
            "eval_case": case,
            "automated_checks": check_summary,
            "model_response": compact_response,
            "rag_context": rag_context,
        },
        indent=2,
    )


def parse_judge_json(raw: str) -> Dict[str, Any]:
    cleaned = re.sub(r"```json|```", "", raw or "").strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            raise
        parsed = json.loads(match.group(0))

    rubric: Dict[str, Any] = {}
    for field in RUBRIC_FIELDS:
        rubric[field] = clamp_score(int(parsed.get(field, 1)))
    rubric["overall_pass"] = bool(parsed.get("overall_pass", False))
    rubric["notes"] = str(parsed.get("notes", "")).strip() or "No judge notes provided."
    return rubric


def llm_judge_score(
    judge: Any,
    case: Dict[str, Any],
    data: Dict[str, Any],
    checks: List[Tuple[bool, str]],
    model: str,
) -> Dict[str, Any]:
    response = judge.generate(
        model=model,
        system=JUDGE_SYSTEM_PROMPT,
        query=judge_query(case, data, checks),
        temperature=0.0,
        rag_usage=False,
        lastk=0,
    )
    if "error" in response:
        raise RuntimeError(response["error"])
    rubric = parse_judge_json(response.get("result", ""))
    rubric["judge_model"] = model
    return rubric


def error_rubric(message: str, model: str | None = None) -> Dict[str, Any]:
    rubric = {
        "role_fit": 1,
        "data_grounding": 1,
        "specificity": 1,
        "rag_retrieval_relevance": 1,
        "rag_grounding_faithfulness": 1,
        "rag_source_relevance": 1,
        "confidence_calibration": 1,
        "safety_no_hallucination": 1,
        "overall_pass": False,
        "notes": message,
    }
    if model:
        rubric["judge_model"] = model
    return rubric


def main() -> int:
    parser = argparse.ArgumentParser(description="Run wildfire report eval cases against local API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--case-id", help="Run a single case by id.")
    parser.add_argument("--score-existing", type=Path, help="Add LLM-judge rubric scores to an existing eval JSON file.")
    parser.add_argument("--judge-model", default="4o-mini", help="LLMProxy model name to use as judge.")
    args = parser.parse_args()
    judge = LLMProxy()

    if args.score_existing:
        existing = json.loads(args.score_existing.read_text())
        rescored = []
        for item in existing:
            case = item["case"]
            if "response" not in item:
                item["rubric"] = error_rubric(item.get("error", "missing response"), args.judge_model)
                rescored.append(item)
                continue
            checks = check_case(case, item["response"])
            item["checks"] = checks
            try:
                item["rubric"] = llm_judge_score(judge, case, item["response"], checks, args.judge_model)
            except Exception as exc:
                item["rubric"] = error_rubric(f"LLM judge failed: {exc}", args.judge_model)
            rescored.append(item)

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = RESULTS_DIR / f"{args.score_existing.stem}_rescored.json"
        out_path.write_text(json.dumps(rescored, indent=2))
        print(f"Saved rescored eval results to {out_path}")
        for item in rescored:
            rubric = item["rubric"]
            score_text = ", ".join(f"{field}={rubric[field]}" for field in RUBRIC_FIELDS)
            print(f"{item['case']['id']}: {score_text}, overall_pass={rubric['overall_pass']} | {rubric['notes']}")
        return 0

    cases = load_cases(args.cases)
    if args.case_id:
        cases = [case for case in cases if case["id"] == args.case_id]
        if not cases:
            raise SystemExit(f"No case found with id: {args.case_id}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"report_eval_{run_id}.json"

    results = []
    total_passed = 0
    total_checks = 0

    for i, case in enumerate(cases, start=1):
        print(f"\n[{i}/{len(cases)}] {case['id']} ({case['user_type']})")
        try:
            data = call_api(args.base_url, case, args.timeout)
            checks = check_case(case, data)
            passed = sum(1 for ok, _ in checks if ok)
            total_passed += passed
            total_checks += len(checks)
            for ok, label in checks:
                print(f"  {'PASS' if ok else 'FAIL'} - {label}")
            rubric = llm_judge_score(judge, case, data, checks, args.judge_model)
            score_text = ", ".join(f"{field}={rubric[field]}" for field in RUBRIC_FIELDS)
            print(f"  RUBRIC - {score_text}, overall_pass={rubric['overall_pass']}")
            print(f"  NOTES - {rubric['notes']}")
            results.append({"case": case, "response": data, "checks": checks, "rubric": rubric})
        except Exception as exc:  # Keep running so one bad case doesn't hide the rest.
            total_checks += 1
            print(f"  ERROR - {exc}")
            rubric = error_rubric(str(exc), args.judge_model)
            results.append({"case": case, "error": str(exc), "checks": [(False, str(exc))], "rubric": rubric})

    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nSaved raw eval results to {out_path}")
    print(f"Summary: {total_passed}/{total_checks} checks passed")
    return 0 if total_passed == total_checks else 1


if __name__ == "__main__":
    raise SystemExit(main())
