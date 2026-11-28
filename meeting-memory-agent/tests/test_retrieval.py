from meeting_memory.retrieval import hybrid_search
from meeting_memory.schemas import Evidence, MemoryItem


def _item(item_id: str, text: str, owner: str | None, kind: str = "commitment") -> MemoryItem:
    return MemoryItem(
        item_id=item_id,
        meeting_id="mtg",
        utterance_id="utt",
        utterance_index=1,
        kind=kind,  # type: ignore[arg-type]
        text=text,
        owner=owner,
        evidence_type="explicit",
        status="open",
        topic_tokens=[],
        evidence=Evidence(
            meeting_id="mtg",
            meeting_name="Planning",
            quote=text,
            source_path="planning.txt",
        ),
    )


def test_hybrid_search_ranks_keywords_and_ignores_unrelated_text():
    migration = _item("itm_db", "I'll handle the database migration.", "John")
    migration.topic_tokens = ["database", "handle", "migration"]
    delivery = _item("itm_api", "Yes, I'll deliver the API implementation by December 5.", "Alex")
    delivery.topic_tokens = ["api", "deliver", "implementation"]
    found = hybrid_search([migration, delivery], "database migration")
    assert found and found[0].item_id == "itm_db"
    assert hybrid_search([migration, delivery], "mobile app") == []
    owned = hybrid_search([migration, delivery], "John", owner="John")
    assert [item.item_id for item in owned] == ["itm_db"]
