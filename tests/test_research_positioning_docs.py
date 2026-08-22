from pathlib import Path


def test_readmes_lead_with_paper_research_core() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_zh = Path("README.zh.md").read_text(encoding="utf-8")

    assert (
        "Control-theoretic diagnostics and reproducible evidence for prompt optimization."
        in readme
    )
    assert "What It Adds" in readme
    assert "Applied Agent Layer" in readme
    assert "pcl research-import peoc" in readme
    assert "pcl research-quickstart" in readme
    assert "pcl research-demo" in readme
    assert "pcl diagnose" in readme
    assert readme.find("What It Adds") < readme.find("Applied Agent Layer")
    assert readme.find("pcl research-import peoc") < readme.find("pcl research-quickstart")
    assert len(readme.splitlines()) <= 40
    assert "docs/research_import_peoc.en.md" in readme
    assert "docs/research_from_paper.en.md" in readme
    assert (
        "Preflight, provenance, and reproducible evaluation for AI coding agents."
        not in readme[:600]
    )

    assert "面向 prompt 优化的控制论诊断与可复现证据工具。" in readme_zh
    assert "它补上了什么" in readme_zh
    assert "Applied Agent Layer" in readme_zh
    assert "pcl research-import peoc" in readme_zh
    assert "pcl research-quickstart" in readme_zh
    assert "pcl research-demo" in readme_zh
    assert "pcl diagnose" in readme_zh
    assert readme_zh.find("它补上了什么") < readme_zh.find("Applied Agent Layer")
    assert readme_zh.find("pcl research-import peoc") < readme_zh.find(
        "pcl research-quickstart"
    )
    assert len(readme_zh.splitlines()) <= 40
    assert "docs/research_import_peoc.zh.md" in readme_zh
    assert "docs/research_from_paper.zh.md" in readme_zh


def test_research_from_paper_docs_map_concepts_to_commands() -> None:
    doc_en = Path("docs/research_from_paper.en.md").read_text(encoding="utf-8")
    doc_zh = Path("docs/research_from_paper.zh.md").read_text(encoding="utf-8")

    for text in [doc_en, doc_zh]:
        assert "pcl research-import peoc" in text
        assert "pcl research-bundle --run runs/peoc-real --verify --strict" in text
        assert "pcl split" in text
        assert "pcl research-quickstart" in text
        assert "pcl research-demo" in text
        assert "pcl diagnose" in text
        assert "pcl stats" in text
        assert "pcl soft-hard" in text
        assert "pcl trajectory" in text
        assert "pcl riccati" in text
        assert "pcl tv-soft" in text

    assert "tri-split withheld protocol" in doc_en
    assert "soft-to-hard projection gap" in doc_en
    assert "hidden-state trajectory" in doc_en
    assert "Riccati surrogate" in doc_en
    assert "time-varying soft-control lane" in doc_en


def test_real_peoc_import_tutorials_are_bilingual_and_fail_closed() -> None:
    tutorial_en = Path("docs/research_import_peoc.en.md").read_text(encoding="utf-8")
    tutorial_zh = Path("docs/research_import_peoc.zh.md").read_text(encoding="utf-8")

    shared_commands = [
        "pcl research-import peoc",
        "pcl claim-check --run runs/peoc-real --claim full-research",
        "pcl gap-status --run runs/peoc-real",
        "pcl research-bundle --run runs/peoc-real --verify --strict",
        "pcl ui --runs runs",
        "pcl soft-hard",
        "pcl trajectory",
        "pcl riccati",
        "pcl tv-soft",
    ]
    for command in shared_commands:
        assert command in tutorial_en
        assert command in tutorial_zh

    for status in ["available", "partial", "failed_validation", "unusable", "missing"]:
        assert status in tutorial_en
        assert status in tutorial_zh

    for phrase in ["Operation", "What you get", "What it means", "Next"]:
        assert phrase in tutorial_en
    for phrase in ["怎么操作", "会得到什么", "这说明什么问题", "下一步"]:
        assert phrase in tutorial_zh

    for text in [tutorial_en, tutorial_zh]:
        assert "source_manifest.json" in text
        assert "peoc_evidence.json" in text
        assert "research_case_study.html" in text
        assert "not a proof" in text.lower() or "不是" in text
        assert "SaaS" not in text
        assert "pricing" not in text.lower()


def test_competitive_positioning_stays_evidence_layer_first() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_zh = Path("README.zh.md").read_text(encoding="utf-8")
    comparison = Path("docs/comparison.en.md").read_text(encoding="utf-8")
    comparison_zh = Path("docs/comparison.zh.md").read_text(encoding="utf-8")
    choice = Path("docs/choice_guide.en.md").read_text(encoding="utf-8")
    choice_zh = Path("docs/choice_guide.zh.md").read_text(encoding="utf-8")
    artifacts = Path("docs/artifacts.en.md").read_text(encoding="utf-8")
    artifacts_zh = Path("docs/artifacts.zh.md").read_text(encoding="utf-8")
    ecosystem = Path("docs/ecosystem_bridge.en.md").read_text(encoding="utf-8")
    ecosystem_zh = Path("docs/ecosystem_bridge.zh.md").read_text(encoding="utf-8")

    assert "pcl import promptfoo" in readme
    assert "pcl import promptfoo" in readme_zh
    assert "docs/choice_guide.en.md" in readme
    assert "docs/choice_guide.zh.md" in readme_zh
    assert "pcl ingest` remains the backward-compatible alias" in readme
    assert "向后兼容别名" in readme_zh

    for text in [comparison, comparison_zh, choice, choice_zh]:
        assert "Promptfoo" in text
        assert "DeepEval" in text
        assert "LangSmith" in text
        assert "Langfuse" in text
        assert "prompt-optimizer" in text

    assert "pcl choose --need prompt-writing" in choice
    assert "pcl choose --need prompt-writing --language zh" in choice_zh
    assert "Five-Minute Adoption Path" in choice
    assert "5 分钟采用路径" in choice_zh
    assert "bridge_summary.html" in choice
    assert "research_bundle.zh.html" in choice_zh
    assert "Shortest Path" in choice
    assert "最短路径" in choice_zh
    assert 'pcl choose --need "<your goal>"' in choice
    assert 'pcl choose --need "<你的目标>" --language zh' in choice_zh

    for text in [choice, choice_zh]:
        assert "pcl start --choice ecosystem" in text
        assert "pcl start --choice import" in text
        assert "pcl evidence-audit" in text
        assert "pcl scaffold-check" in text

    for text in [artifacts, artifacts_zh]:
        assert "market_readiness" in text

    for text in [ecosystem, ecosystem_zh]:
        assert "Market readiness" in text
        assert (
            "pcl ecosystem-demo --examples examples/external --out runs/ecosystem-demo "
            "--summary"
            in text
        )
        assert "pcl ecosystem-scorecard --run runs/ecosystem-demo --summary" in text

    for text in [comparison, comparison_zh]:
        assert "evidence-audit" in text
        assert "claim-check" in text
        assert "gap-status" in text

    assert "How PCL Can Beat Adjacent Tools Without Rebuilding Them" in comparison
    assert "Do not rebuild prompt-optimizer's prompt editor" in comparison
    assert "Use prompt-optimizer when you want a better prompt writing interface" in comparison
    assert "Promptfoo intro" in comparison
    assert "DeepEval introduction" in comparison
    assert "Langfuse docs" in comparison
    assert "linshenkx/prompt-optimizer README" in comparison
    assert "Extended Market Map" in comparison
    assert "Braintrust" in comparison
    assert "Arize Phoenix" in comparison
    assert "OpenAI Evals" in comparison
    assert "Humanloop" in comparison
    assert "2025-09-08 sunset" in comparison_zh
