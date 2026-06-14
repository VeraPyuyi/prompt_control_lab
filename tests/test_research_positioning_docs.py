from pathlib import Path


def test_readmes_lead_with_paper_research_core() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_zh = Path("README.zh.md").read_text(encoding="utf-8")

    assert (
        "Control-theoretic diagnostics and reproducible evaluation for prompt optimization."
        in readme
    )
    assert "Research Core" in readme
    assert "Applied Engineering Layer" in readme
    assert "pcl research-demo" in readme
    assert "pcl diagnose" in readme
    assert readme.find("Research Core") < readme.find("Local Case Studies")
    assert "docs/research_from_paper.en.md" in readme
    assert (
        "Preflight, provenance, and reproducible evaluation for AI coding agents."
        not in readme[:600]
    )

    assert "面向 prompt 优化的控制论诊断与可复现评测工具。" in readme_zh
    assert "研究内核" in readme_zh
    assert "工程应用层" in readme_zh
    assert "pcl research-demo" in readme_zh
    assert "pcl diagnose" in readme_zh
    assert readme_zh.find("研究内核") < readme_zh.find("本地 Case Study")
    assert "docs/research_from_paper.zh.md" in readme_zh


def test_research_from_paper_docs_map_concepts_to_commands() -> None:
    doc_en = Path("docs/research_from_paper.en.md").read_text(encoding="utf-8")
    doc_zh = Path("docs/research_from_paper.zh.md").read_text(encoding="utf-8")

    for text in [doc_en, doc_zh]:
        assert "pcl split" in text
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

    assert "三段切分" in doc_zh
    assert "软转硬" in doc_zh
    assert "hidden-state trajectory" in doc_zh
    assert "Riccati surrogate" in doc_zh
    assert "time-varying soft-control" in doc_zh


def test_competitive_positioning_stays_evidence_layer_first() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_zh = Path("README.zh.md").read_text(encoding="utf-8")
    comparison = Path("docs/comparison.en.md").read_text(encoding="utf-8")
    comparison_zh = Path("docs/comparison.zh.md").read_text(encoding="utf-8")

    assert "pcl import promptfoo" in readme
    assert "pcl import promptfoo" in readme_zh
    assert "pcl ingest` is kept as the backward-compatible alias" in readme
    assert "兼容别名" in readme_zh

    for text in [comparison, comparison_zh]:
        assert "Promptfoo" in text
        assert "LangSmith" in text
        assert "Langfuse" in text
        assert "prompt-optimizer" in text
        assert "evidence-audit" in text
        assert "claim-check" in text
        assert "gap-status" in text

    assert "How PCL Can Beat Adjacent Tools Without Rebuilding Them" in comparison
    assert "Do not rebuild prompt-optimizer's prompt editor" in comparison
    assert "Use prompt-optimizer when you want a better prompt writing interface" in comparison
    assert "不重造竞品" in comparison_zh
    assert "超过它们的方式" in comparison_zh
    assert "不要重造 prompt-optimizer 的 prompt 编辑器" in comparison_zh
    assert "想写出更好的 prompt" in comparison_zh
    assert "用 prompt-optimizer" in comparison_zh
    assert "Promptfoo intro" in comparison
    assert "Langfuse docs" in comparison
    assert "linshenkx/prompt-optimizer README" in comparison
