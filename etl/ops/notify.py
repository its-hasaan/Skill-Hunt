"""
Pipeline summary + failure alert email (Resend free tier).

    python -m ops.notify --results "preflight=success,adzuna=skipped,ingest=failure,..."

--results comes from the workflow's step outcomes, so the alert still goes
out when the database itself is down (the ledger then can't be read).
Without a verified domain, Resend's onboarding@resend.dev sender can only
deliver to the Resend account's own email, which is what ALERT_EMAIL is.
Exits 1 when any step failed so the workflow run shows as failed.
"""
from __future__ import annotations

import argparse
import os
import sys

import requests

from ops import ledger
from ops.dbconfig import load_local_env, session_pooler_url

RESEND_ENDPOINT = "https://api.resend.com/emails"
DEFAULT_SENDER = "Jobwise Pipeline <onboarding@resend.dev>"
FAILED_OUTCOMES = {"failure", "cancelled"}
ERROR_CHARS = 3000


def parse_results(text: str) -> dict[str, str]:
    results = {}
    for piece in filter(None, (p.strip() for p in text.split(","))):
        step, sep, outcome = piece.partition("=")
        if not sep or not step:
            raise ValueError(f"bad --results entry: {piece!r} (expected step=outcome)")
        results[step.strip()] = outcome.strip() or "skipped"
    return results


def build_summary(results, ledger_rows, run_url=None):
    failed = [step for step, outcome in results.items() if outcome in FAILED_OUTCOMES]
    subject = "[Jobwise pipeline] " + ("FAILED: " + ", ".join(failed) if failed else "OK")
    lines = ["Step outcomes:"]
    lines += [f"  {step:<10} {outcome}" for step, outcome in results.items()]
    metrics = [r for r in ledger_rows if r.get("rows_out") is not None]
    if metrics:
        lines += ["", "Metrics:"]
        lines += [f"  {r['step']}: {(r.get('details') or {}).get('metric', 'rows')}={r['rows_out']}"
                  for r in metrics]
    errors = {r["step"]: r["error"] for r in ledger_rows if r.get("error")}
    for step in failed:
        if step in errors:
            lines += ["", f"--- {step}: last output ---", errors[step][-ERROR_CHARS:]]
    if run_url:
        lines += ["", f"Run: {run_url}"]
    return subject, "\n".join(lines), bool(failed)


def send_via_resend(api_key, to, subject, text, http=requests, sender=DEFAULT_SENDER):
    resp = http.post(RESEND_ENDPOINT, json={"from": sender, "to": [to], "subject": subject, "text": text},
                     headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
    resp.raise_for_status()


def main(argv=None, env=None) -> int:
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description="Summarise a pipeline run; email on failure")
    parser.add_argument("--results", required=True, help="comma-separated step=outcome pairs")
    parser.add_argument("--always", action="store_true", help="email even when every step passed")
    args = parser.parse_args(argv)

    results = parse_results(args.results)
    url = session_pooler_url(env.get("SUPABASE_URL"))
    rows = ledger.fetch_run(url, ledger.current_run_id(env)) if url else []
    run_url = None
    if env.get("GITHUB_RUN_ID"):
        run_url = (f"{env.get('GITHUB_SERVER_URL', 'https://github.com')}/"
                   f"{env.get('GITHUB_REPOSITORY')}/actions/runs/{env['GITHUB_RUN_ID']}")
    subject, body, has_failure = build_summary(results, rows, run_url)
    print(subject)
    print(body)

    if has_failure or args.always:
        key, to = env.get("RESEND_API_KEY"), env.get("ALERT_EMAIL")
        if key and to:
            try:
                send_via_resend(key, to, subject, body)
            except requests.RequestException as exc:
                print(f"::warning::Alert email failed: {exc.__class__.__name__}")
        else:
            print("::warning::RESEND_API_KEY / ALERT_EMAIL not set; no email sent")
    return 1 if has_failure else 0


if __name__ == "__main__":
    load_local_env()
    sys.exit(main())
