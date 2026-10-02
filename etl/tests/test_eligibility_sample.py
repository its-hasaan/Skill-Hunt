from ops import eligibility_sample as es


def row(job_id, pk, inn=None, stratum="pk_yes"):
    return {"job_id": job_id, "stratum": stratum, "title": "Data Engineer", "company_name": "Acme",
            "source": "lever", "location_display": "Remote", "location_areas": ["Remote", "Asia"],
            "eligible_pk": pk, "eligible_in": inn, "remote_scope": "regions", "eligibility_confidence": 0.7,
            "eligibility_method": "rules", "eligibility_evidence": "Asia",
            "description": "We love Python. You can be based anywhere in Asia.", "apply_url": "https://x/1"}


def test_render_lists_labels_evidence_and_location_sentences():
    text = es.render([row(1, True, True)], {"pk_yes": 10})
    assert "### 1. Data Engineer — Acme (lever)" in text
    assert "pk=**yes** in=**yes**" in text and "Asia" in text
    assert "You can be based anywhere in Asia." in text and "We love Python" not in text
    assert "- Verdict:" in text


def test_strata_weights_are_reported():
    text = es.render([row(1, False, False, "pk_no"), row(2, None, None, "unclear")], {"pk_no": 300, "unclear": 20})
    assert "pk_no: 1 sampled of 300" in text and "unclear: 1 sampled of 20" in text


def test_label_words():
    assert [es.word(v) for v in (True, False, None)] == ["yes", "no", "unclear"]
