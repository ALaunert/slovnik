"""Read-only analysis of explicitly declared observer facts; never infer missing contacts."""

from datetime import datetime, timedelta


def _time(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Observer times must have a timezone")
    return result


def _unique(records):
    seen = {}
    for record in records:
        if record["id"] in seen and seen[record["id"]] != record:
            raise ValueError("Duplicate ID has conflicting immutable first-response facts")
        seen[record["id"]] = record
    return tuple(seen.values())


def _observations(history):
    """Inventory timestamps before analysis; invitation order is not contact order."""
    contacts, unknown = [], []
    for kind, records in (("presentation", history.get("presentations", [])), ("activity", history["activities"])):
        for record in _unique(records):
            offered = _time(record["offered_at"])
            owner = record["id"] if kind == "activity" else record.get("activity_id")
            family = record["context_family"]
            response = record.get("response")
            responded = _time(response["at"]) if response else None
            status = record.get("display_status")
            if status not in {None, "shown", "not_shown", "unknown"}:
                raise ValueError("Unknown observer display status")
            if responded is not None:
                if responded < offered:
                    raise ValueError("Response cannot precede invitation")
                contacts.append((responded, family, owner, "response"))
            if status == "shown":
                shown = _time(record["shown_at"])
                if shown < offered or (responded is not None and shown > responded):
                    raise ValueError("Display must follow invitation and precede response")
                contacts.append((shown, family, owner, "display"))
            elif responded is not None and status == "not_shown":
                raise ValueError("An answered task cannot be declared not shown")
            elif response is None and status != "not_shown":
                unknown.append(offered)
            support = record.get("support", "unknown")
            if support in {"hint", "reveal", "correction"}:
                if record.get("support_at"):
                    support_at = _time(record["support_at"])
                    if support_at < offered:
                        raise ValueError("Support cannot precede invitation")
                    contacts.append((support_at, family, owner, "support"))
                else:
                    unknown.append(offered)
    return contacts, unknown


def summarize_history(history):
    """One learner/target/capability/modality history; ratios remain counts with missingness."""
    counts = {key: [0, 0] for key in ("presentations", "first_unaided", "assisted", "retry",
                                      "self_report", "same_context", "unresolved")}
    counts.update({"delayed_7d": [0]*5, "delayed_28d": [0]*5, "display_unknown": 0,
                   "probe_unknown": 0, "probe_excluded": 0, "unanswered": 0, "support_unknown": 0,
                   "probe_observations": []})
    all_contacts, unknown_observations = _observations(history)
    presentations = _unique(history.get("presentations", []))
    for presentation in presentations:
        status = presentation.get("display_status", "unknown")
        if status not in {"shown", "not_shown", "unknown"}:
            raise ValueError("Unknown observer display status")
        if status == "unknown":
            counts["display_unknown"] += 1
            continue
        counts["presentations"][1] += 1
        if status == "shown":
            shown = _time(presentation["shown_at"])
            if shown < _time(presentation["offered_at"]):
                raise ValueError("Display cannot precede invitation")
            counts["presentations"][0] += 1
    by_id = {activity["id"]: activity for activity in _unique(history["activities"])}
    for activity in sorted(_unique(history["activities"]), key=lambda item: (_time(item["offered_at"]), item["id"])):
        offered = _time(activity["offered_at"])
        family = activity["context_family"]
        response, retry = activity.get("response"), activity.get("retry_of")
        responded = _time(response["at"]) if response else None
        shown = _time(activity["shown_at"]) if activity.get("display_status") == "shown" else None
        observed = shown or responded
        cutoff = responded or observed or offered
        def own_contact(at, context, owner, kind):
            return owner == activity["id"] and (kind == "response" or (
                kind == "display" and shown is not None and at == shown and context == family))
        repeated = any(context == family and at < cutoff and not own_contact(at, context, owner, kind)
                       for at, context, owner, kind in all_contacts)
        complete = (history.get("history_complete") is True
                    and not any(at <= cutoff for at in unknown_observations))
        support = activity.get("support", "unknown")
        support_known = history.get("support_capture_complete") is True and support == "none"
        supported = False
        if support in {"hint", "reveal", "correction"} and response and activity.get("support_at"):
            supported = offered <= _time(activity["support_at"]) < _time(response["at"])
            support_known = supported
        parent = by_id.get(retry)
        retry_known = bool(parent and parent["context_family"] == family and parent.get("response")
                           and _time(parent["response"]["at"]) < offered)
        horizon = activity.get("probe_horizon_days")
        probe = None
        if horizon is not None:
            if type(horizon) is not int or horizon not in {7, 28}:
                raise ValueError("Probe horizon must be seven or twenty-eight days")
            probe = counts[f"delayed_{horizon}d"]
            probe[2] += 1
            if response is None:
                probe[3] += 1
            elif response.get("outcome") == "unresolved":
                probe[4] += 1
            prior_contacts = [(at, context) for at, context, owner, kind in all_contacts
                              if observed is not None and at < observed and not own_contact(at, context, owner, kind)]
            unknown = (history.get("history_complete") is not True or not support_known or not prior_contacts
                       or shown is None or any(at <= (responded or observed) for at in unknown_observations))
            eligible = False
            reasons = []
            if unknown:
                counts["probe_unknown"] += 1
                if history.get("history_complete") is not True:
                    reasons.append("history_incomplete")
                if not support_known:
                    reasons.append("support_unknown_or_present")
                if not prior_contacts:
                    reasons.append("latest_contact_unknown")
                if shown is None:
                    reasons.append("probe_contact_unknown")
                if any(at <= (responded or observed or offered) for at in unknown_observations):
                    reasons.append("unknown_contact")
            else:
                latest = max(at for at, _ in prior_contacts)
                # Narrow protocol windows within the broader P0 non-overlapping bands.
                upper = 10 if horizon == 7 else 31
                in_window = (timedelta(days=horizon) <= observed-latest < timedelta(days=upper)
                             and (responded is None or timedelta(days=horizon) <= responded-latest < timedelta(days=upper)))
                intervening = responded is not None and any(
                    observed <= at <= responded and not own_contact(at, context, owner, kind)
                    for at, context, owner, kind in all_contacts)
                probe_repeated = any(context == family for _, context in prior_contacts)
                eligible = (in_window and not intervening
                            and not probe_repeated and retry is None and support == "none"
                            and history.get("key_frozen") is True)
                if not eligible:
                    counts["probe_excluded"] += 1
                    if not in_window:
                        reasons.append("outside_window")
                    if intervening:
                        reasons.append("intervening_contact")
                    if probe_repeated:
                        reasons.append("familiar_family")
                    if retry is not None:
                        reasons.append("retry")
                    if support != "none":
                        reasons.append("assisted")
                    if history.get("key_frozen") is not True:
                        reasons.append("key_not_frozen")
            counts["probe_observations"].append({
                "id": activity["id"], "horizon_days": horizon,
                "display_status": activity.get("display_status", "unknown"),
                "responded": response is not None, "missing": response is None,
                "resolved": response is not None and response.get("outcome") in {"correct", "incorrect"},
                "unresolved": response is not None and response.get("outcome") == "unresolved",
                "eligibility": "unknown" if unknown else "eligible" if eligible else "excluded",
                "reasons": reasons})
        if response is None:
            counts["unanswered"] += 1
        else:
            responded = _time(response["at"])
            if responded < offered:
                raise ValueError("Response cannot precede invitation")
            if response["kind"] == "self_report":
                if response.get("rating") not in {"again", "hard", "good", "easy"}:
                    raise ValueError("Unknown self-rating")
                counts["self_report"][1] += 1
                counts["self_report"][0] += response["rating"] in {"good", "easy"}
            elif response["kind"] == "scored":
                outcome = response.get("outcome")
                if outcome not in {"correct", "incorrect", "unresolved"}:
                    raise ValueError("Unknown objective verdict")
                counts["unresolved"][1] += 1
                counts["unresolved"][0] += outcome == "unresolved"
                if outcome in {"correct", "incorrect"} and history.get("key_frozen") is True:
                    bucket = None
                    if retry is not None:
                        bucket = "retry" if retry_known else None
                    elif supported:
                        bucket = "assisted"
                    elif support_known and complete:
                        bucket = "same_context" if repeated else "first_unaided"
                    if bucket:
                        counts[bucket][1] += 1
                        counts[bucket][0] += outcome == "correct"
                    else:
                        counts["support_unknown"] += 1
                    if probe is not None and eligible:
                        probe[1] += 1
                        probe[0] += outcome == "correct"
            else:
                raise ValueError("Unknown response kind")
    return counts
