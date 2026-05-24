from pathlib import Path
from dqbench.adapters.base import DQBenchAdapter
from dqbench.models import DQBenchFinding


class MockAdapter(DQBenchAdapter):
    @property
    def name(self): return "MockTool"

    @property
    def version(self): return "1.0"

    def validate(self, csv_path):
        return [DQBenchFinding(column="test", severity="error", check="test", message="test")]


def test_mock_adapter():
    adapter = MockAdapter()
    assert adapter.name == "MockTool"
    findings = adapter.validate(Path("fake.csv"))
    assert len(findings) == 1


def test_goldensuite_adapters_registered():
    from dqbench.adapters.base import PipelineAdapter
    from dqbench.adapters.goldenpipe_adapter import (
        GoldenSuiteTunedAdapter,
        GoldenSuiteZeroConfigAdapter,
    )
    from dqbench.cli import BUILTIN_ADAPTERS, PIPELINE_ADAPTER_NAMES

    for name in ("goldensuite-zero", "goldensuite-tuned"):
        assert name in BUILTIN_ADAPTERS
        assert name in PIPELINE_ADAPTER_NAMES

    assert GoldenSuiteZeroConfigAdapter().name == "GoldenSuite (zero-config)"
    assert GoldenSuiteTunedAdapter().name == "GoldenSuite (tuned)"
    assert isinstance(GoldenSuiteTunedAdapter(), PipelineAdapter)


def test_third_party_adapters_registered():
    from dqbench.adapters.base import (
        DQBenchAdapter,
        EntityResolutionAdapter,
        TransformAdapter,
    )
    from dqbench.cli import BUILTIN_ADAPTERS, _load_adapter

    expected = {
        "recordlinkage": EntityResolutionAdapter,
        "cuallee": DQBenchAdapter,
        "frictionless": DQBenchAdapter,
        "pandas-transform": TransformAdapter,
    }
    for name, base in expected.items():
        assert name in BUILTIN_ADAPTERS, name
        adapter = _load_adapter(name)  # instantiation must not require the tool installed
        assert isinstance(adapter, base), name
        assert adapter.name


def test_assemble_dedup_output_keeps_rowid_and_drops_internal():
    import polars as pl

    from dqbench.adapters.goldenpipe_adapter import _assemble_dedup_output

    unique = pl.DataFrame({"_row_id": [1], "first_name": ["A"], "__mk_x__": [9]})
    dupes = pl.DataFrame({"_row_id": [2, 3], "first_name": ["B", "B"], "__row_id__": [2, 3]})
    clusters = {1: {"members": [2, 3]}}

    out = _assemble_dedup_output(unique, dupes, None, clusters)

    assert "_row_id" in out.columns
    assert not any(c.startswith("__") for c in out.columns)
    # one unique record + one representative (lowest _row_id) per cluster
    assert out.height == 2
    assert sorted(out["_row_id"].to_list()) == [1, 2]
