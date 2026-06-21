"""
Interactive CLI for Event Extraction and Human Review.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from relay.db.event_store import EventStore
from relay.schema.events import EventMetadata, EventType
from relay.extraction.extractor import extract_observations
from relay.extraction.suggestor import suggest_events
from relay.extraction.validator import validate_candidate_event


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract events from agent output file.")
    parser.add_argument("--project-id", required=True, help="UUID of the project")
    parser.add_argument("--file", required=True, help="Path to the agent output text/markdown file")
    args = parser.parse_args()

    pid = uuid.UUID(args.project_id)
    file_path = Path(args.file)

    if not file_path.exists():
        print(f"Error: File not found at {file_path}")
        sys.exit(1)

    text = file_path.read_text(encoding="utf-8")

    # Stage A: Extract raw observations
    observations = extract_observations(text)
    print(f"\n[EXTRACTOR] Extracted {len(observations)} raw observations.")

    # Stage B: Suggest candidate events
    candidates = suggest_events(text, observations)
    print(f"[SUGGESTOR] Suggested {len(candidates)} candidate events.")

    store = EventStore()
    meta = EventMetadata(
        actor="HumanReviewer",
        source="extract_events_cli",
        correlation_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4())
    )

    audit_records = []
    committed_count = 0

    for idx, cand in enumerate(candidates, start=1):
        print("\n" + "=" * 50)
        print(f"Candidate Event #{idx} of {len(candidates)}")
        print(f"Type:       {cand.event_type}")
        print(f"Stream:     {cand.stream_id}")
        print(f"Confidence: {cand.confidence:.2f}")
        print(f"Payload:    {json.dumps(cand.payload, indent=2)}")
        if cand.backing_observation:
            print(f"Backing:    \"{cand.backing_observation}\"")
        
        is_valid = validate_candidate_event(cand)
        print(f"Validation: {'[PASS]' if is_valid else '[FAIL - Invalid Schema]'}")

        decision = None
        while True:
            choice = input("Decision ([y] approve, [n] reject, [e] edit): ").strip().lower()
            if choice == "y":
                decision = "approved"
                if not is_valid:
                    print("Warning: committing an event that failed schema validation.")
                store.append_event(
                    pid,
                    cand.stream_id,
                    EventType(cand.event_type),
                    cand.payload,
                    meta
                )
                print("Event committed to ledger.")
                committed_count += 1
                break
            elif choice == "n":
                decision = "rejected"
                print("Event rejected.")
                break
            elif choice == "e":
                print("Enter new JSON payload (press Enter then Ctrl-D or Ctrl-Z on Windows to complete input):")
                lines = []
                while True:
                    try:
                        line = input()
                        lines.append(line)
                    except EOFError:
                        break
                raw_json = "".join(lines).strip()
                try:
                    new_payload = json.loads(raw_json)
                    cand.payload = new_payload
                    is_valid = validate_candidate_event(cand)
                    print(f"\nUpdated Payload: {json.dumps(cand.payload, indent=2)}")
                    print(f"Validation: {'[PASS]' if is_valid else '[FAIL - Invalid Schema]'}")
                except Exception as ex:
                    print(f"Error parsing JSON: {ex}. Try editing again.")
            else:
                print("Invalid choice. Enter y, n, or e.")

        audit_records.append({
            "candidate": {
                "event_type": cand.event_type,
                "stream_id": cand.stream_id,
                "payload": cand.payload,
                "confidence": cand.confidence,
                "backing_observation": cand.backing_observation
            },
            "decision": decision,
            "validated": is_valid
        })

    # Save session record to tests/extraction_audit/
    audit_dir = Path("tests/extraction_audit")
    audit_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    audit_file = audit_dir / f"{timestamp}_{pid}.json"
    audit_file.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_id": str(pid),
        "file_parsed": str(file_path),
        "total_candidates": len(candidates),
        "total_committed": committed_count,
        "session_log": audit_records
    }, indent=2), encoding="utf-8")

    print("\n" + "=" * 50)
    print(f"Review session completed. Committed {committed_count} events.")
    print(f"Audit log written to: {audit_file.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
