import pytest
import uuid
import json
from rationalevault.schema.events import EventType
from rationalevault.governance.state import GovernanceSeverity, GovernanceAction

from rationalevault.db.sqlite_store import SQLiteEventStore

@pytest.fixture
def temp_project(tmp_path):
    project_id = uuid.uuid4()
    db_file = tmp_path / "test.db"
    store = SQLiteEventStore(db_path=str(db_file))
    return project_id, store

def test_cli_respects_ledger_rules(temp_project, capsys, monkeypatch):
    from rationalevault.cli.main import main
    project_id, store = temp_project
    
    # Mock _resolve_project_id to return our temp project
    import rationalevault.cli.main
    monkeypatch.setattr(rationalevault.cli.main, "_resolve_project_id", lambda: project_id)
    
    # Mock EventStore instantiation to return our temp store
    from rationalevault.db.event_store import EventStore
    monkeypatch.setattr(rationalevault.projection_platform.compiler, "EventStore", lambda: store)
    
    # 1. Run without rules -> should show "No governance rules configured"
    import sys
    monkeypatch.setattr(sys, "argv", ["rv", "governance", "show"])
    try:
        main()
    except SystemExit:
        pass
    
    captured = capsys.readouterr()
    assert "No governance rules configured" in captured.out
    
    from rationalevault.schema.events import EventMetadata
    # 2. Emit GOVERNANCE_RULE_CREATED with a custom rule
    store.append_event(
        project_id=project_id,
        stream_id="governance",
        event_type=EventType.GOVERNANCE_RULE_CREATED,
        metadata=EventMetadata(actor="test", source="test"),
        payload={
            "metadata": {
                "id": "test_cli_rule",
                "version": 1,
                "description": "Custom rule for testing",
                "severity": "critical",
                "action": "block"
            },
            "condition": {
                "minimum_priority": 0.1
            },
            "enabled": True
        }
    )
    
    # We also need a fake recommendation or knowledge to trigger the rule so it shows up?
    # If the rule exists but doesn't trigger, does it show in 'show'?
    # Actually, `governance show` only shows *warnings*, not the rules themselves.
    # To get a warning, the rule must be matched by evidence!
    # Let's emit a KNOWLEDGE_CREATED event so RecommendationProjection creates a recommendation that triggers the rule.
    store.append_event(
        project_id=project_id,
        stream_id="knowledge",
        event_type=EventType.KNOWLEDGE_CREATED,
        metadata=EventMetadata(actor="test", source="test"),
        payload={
            "knowledge_id": "k1",
            "title": "A bad thing happened",
            "content": "This is very bad",
            "knowledge_type": "decision",
            "knowledge_domain": "architecture",
            "tags": [],
            "importance": "high"
        }
    )
    
    # 3. Run governance show
    monkeypatch.setattr(sys, "argv", ["rv", "governance", "show"])
    try:
        main()
    except SystemExit:
        pass
        
    captured = capsys.readouterr()
    
    # We should see the warning from the custom rule
    assert "test_cli_rule" in captured.out
    assert "CRITICAL" in captured.out
    assert "BLOCK" in captured.out
    
    # 4. Emit GOVERNANCE_RULE_DELETED
    store.append_event(
        project_id=project_id,
        stream_id="governance",
        event_type=EventType.GOVERNANCE_RULE_DELETED,
        metadata=EventMetadata(actor="test", source="test"),
        payload={
            "rule_id": "test_cli_rule",
            "version": 1
        }
    )
    
    # 5. Run again, should have no rules configured or no warnings
    monkeypatch.setattr(sys, "argv", ["rv", "governance", "show"])
    try:
        main()
    except SystemExit:
        pass
        
    captured = capsys.readouterr()
    assert "No governance rules configured" in captured.out
