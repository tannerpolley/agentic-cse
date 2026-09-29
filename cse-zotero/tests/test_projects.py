import pytest

from zotero_companion.projects import (
    GENERATED_MARKER,
    ProjectError,
    collection_table,
    memberships,
    plan_registration,
    sync_projects,
)

COLLECTIONS = [
    {"key": "ROOT0001", "data": {"name": "Project Libraries"}},
    {"key": "PROJ0001", "data": {"name": "MEA Paper", "parentCollection": "ROOT0001"}},
    {"key": "DATA0001", "data": {"name": "Data", "parentCollection": "PROJ0001"}},
    {"key": "VLE00001", "data": {"name": "VLE", "parentCollection": "DATA0001"}},
    {"key": "PROJ0002", "data": {"name": "Lithium Paper", "parentCollection": "ROOT0001"}},
    {"key": "OTHER001", "data": {"name": "Textbooks"}},
]
ITEMS = [
    {"key": "ITEM0001", "data": {"itemType": "journalArticle", "title": "Nested  VLE data",
                                 "creators": [{"creatorType": "author", "lastName": "Aronu"},
                                              {"creatorType": "author", "lastName": "Kim"},
                                              {"creatorType": "author", "lastName": "Svendsen"}],
                                 "date": "2011-03", "collections": ["VLE00001"]}},
    {"key": "ITEM0002", "data": {"itemType": "book", "title": "Direct member",
                                 "creators": [{"creatorType": "author", "lastName": "Prausnitz"}],
                                 "collections": ["PROJ0001", "OTHER001"]}},
    {"key": "ITEM0003", "data": {"itemType": "book", "title": "Unrelated", "collections": ["OTHER001"]}},
]
REGISTRY = {
    "version": 1,
    "root_collection": "ROOT0001",
    "sync_command": [],
    "projects": {"mea": {"collection": "PROJ0001", "repository": "/repos/mea"}},
}


def test_membership_follows_nested_collections_not_names():
    table = collection_table(COLLECTIONS)
    projects = {"mea": "PROJ0001", "lithium": "PROJ0002"}
    assert memberships(["VLE00001"], table, projects) == ["mea"]
    assert memberships(["OTHER001"], table, projects) == []


def test_sync_renders_tree_below_preserved_curated_notes(tmp_path):
    wiki = tmp_path / "wiki"
    page = wiki / "projects" / "mea.md"
    page.parent.mkdir(parents=True)
    page.write_text("# MEA\n\nHand-written orientation.\n", encoding="utf-8")
    (wiki / "sources" / "ITEM0001").mkdir(parents=True)
    (wiki / "sources" / "ITEM0001" / "source.md").write_text("", encoding="utf-8")

    first = sync_projects(REGISTRY, wiki, collections=COLLECTIONS, items=ITEMS, apply=True)
    text = page.read_text(encoding="utf-8")
    curated, generated = text.split(GENERATED_MARKER)
    assert curated == "# MEA\n\nHand-written orientation.\n\n"
    assert "2 papers" in generated
    assert generated.index("Prausnitz (n.d.). *Direct member*.") < generated.index("### Data (1)")
    assert "#### VLE (1)\n\n- Aronu et al. (2011). *Nested VLE data*. [source](../sources/ITEM0001/source.md)" in generated
    assert "Unrelated" not in generated
    assert first["stale"] == ["mea"]

    page.write_text(text.replace("Hand-written orientation.", "Edited notes."), encoding="utf-8")
    moved = [dict(c) for c in COLLECTIONS]
    moved[3] = {"key": "VLE00001", "data": {"name": "VLE", "parentCollection": "PROJ0001"}}
    assert sync_projects(REGISTRY, wiki, collections=moved, items=ITEMS)["stale"] == ["mea"]
    sync_projects(REGISTRY, wiki, collections=moved, items=ITEMS, apply=True)
    updated = page.read_text(encoding="utf-8")
    assert "Edited notes." in updated and "### VLE (1)" in updated
    assert sync_projects(REGISTRY, wiki, collections=moved, items=ITEMS)["stale"] == []


def test_registration_is_limited_to_disjoint_collections_under_the_root():
    proposed = plan_registration(REGISTRY, slug="lithium", collection="PROJ0002",
                                 repository="/repos/li", collections=COLLECTIONS)
    assert proposed["projects"]["lithium"] == {"collection": "PROJ0002", "repository": "/repos/li"}
    for collection in ("OTHER001", "ROOT0001", "DATA0001"):
        with pytest.raises(ProjectError):
            plan_registration(REGISTRY, slug="other", collection=collection,
                              repository="", collections=COLLECTIONS)


def test_missing_project_collection_is_reported_without_blocking_others(tmp_path):
    registry = {**REGISTRY, "projects": {**REGISTRY["projects"],
                                         "gone": {"collection": "TRASHED1", "repository": ""}}}
    result = sync_projects(registry, tmp_path, collections=COLLECTIONS, items=ITEMS, apply=True)
    assert result["missing"] == ["gone"]
    assert result["stale"] == ["mea"] and (tmp_path / "projects" / "mea.md").exists()
    assert not (tmp_path / "projects" / "gone.md").exists()
