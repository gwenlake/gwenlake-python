"""``@incremental``: an Output that reads itself, and writes that add to it.

A fake client stands in for the catalog: datasets and files are dicts, a
``SELECT`` answers the output's rows as Arrow, and every call is recorded so
a test can say what the handle did, not only what it returned.
"""

import io
import re

import pandas as pd
import pyarrow as pa
import pytest

from gwenlake.exceptions import GwenlakeException
from gwenlake.transforms import (
    Connection,
    IncrementalTransformInput,
    IncrementalTransformOutput,
    Input,
    Output,
    incremental,
    train,
    transform,
    transform_df,
)


# ---------------------------------------------------------------------------
# A catalog in memory
# ---------------------------------------------------------------------------

def _ipc(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    with pa.ipc.new_file(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()


class _Dataset:
    def __init__(self, id, alias, dtype="files", rows=None, files=()):
        self.id, self.alias, self.type = id, alias, dtype
        self.rows = rows if rows is not None else pd.DataFrame()
        self.files = list(files)


class FakeClient:
    """Enough of ``Gwenlake`` for the transforms module: one project ``p``."""

    def __init__(self, *datasets: _Dataset):
        self._datasets = {d.id: d for d in datasets}
        self.calls = []
        client = self

        class Projects:
            def list(self_):
                return [{"id": "res.project.p", "alias": "p"}]

        class Datasets:
            def list(self_, project_id=None, **_):
                return [{"id": d.id, "alias": d.alias, "parent_id": "res.project.p"} for d in client._datasets.values()]

            def get(self_, id):
                return {"id": id, "type": client._datasets[id].type}

            def empty(self_, id, *, branch=None):
                client.calls.append(("empty", id, branch))
                client._datasets[id].files.clear()
                client._datasets[id].rows = client._datasets[id].rows.iloc[0:0]
                return True

        class Files:
            def list(self_, dataset_id, path=None, *, branch=None):
                client.calls.append(("list", dataset_id, path, branch))
                return [{"path": f, "filename": f.rsplit("/", 1)[-1], "size": 1} for f in client._datasets[dataset_id].files]

            def upload(self_, dataset_id, data, *, path=None, filename=None, mode=None, branch=None):
                client.calls.append(("upload", dataset_id, filename, mode, branch))
                client._datasets[dataset_id].files.append(filename)
                return {"filename": filename}

            def delete(self_, dataset_id, filepath, *, branch=None):
                client.calls.append(("delete", dataset_id, filepath, branch))
                client._datasets[dataset_id].files.remove(filepath)
                return True

            def download(self_, dataset_id, filepath, *, branch=None):
                client.calls.append(("download", dataset_id, filepath, branch))
                return b"bytes of " + filepath.encode()

        class Statements:
            def create(self_, statement, format="pyarrow", timeout=None):
                client.calls.append(("select", statement))
                m = re.search(r"FROM 'p\.([^':]+)", statement)
                ds = next(d for d in client._datasets.values() if d.alias == m.group(1))
                rows = ds.rows
                cols = re.match(r"SELECT (.+) FROM", statement).group(1)
                if cols != "*":
                    rows = rows[[c.strip('"') for c in cols.split(", ")]]
                if "OFFSET" in statement:
                    offset = int(re.search(r"OFFSET (\d+)", statement).group(1))
                    limit = int(re.search(r"LIMIT (\d+)", statement).group(1))
                    rows = rows.iloc[offset:offset + limit]
                return _ipc(pa.Table.from_pandas(rows, preserve_index=False))

        self.projects, self.datasets, self.files, self.statements = Projects(), Datasets(), Files(), Statements()

    def of(self, kind):
        return [c for c in self.calls if c[0] == kind]


@pytest.fixture
def log_rows():
    return pd.DataFrame({"path": ["a.pdf", "b.pdf"], "size": [1, 2]})


@pytest.fixture
def client(log_rows):
    return FakeClient(
        _Dataset("res.dataset.log", "log", rows=log_rows, files=["part-old-00000.parquet"]),
        _Dataset("res.dataset.fresh", "fresh"),
        _Dataset("res.dataset.ice", "ice", dtype="iceberg", rows=log_rows, files=["data/x.parquet"]),
        _Dataset("res.dataset.vec", "vec", dtype="vector"),
    )


@pytest.fixture(autouse=True)
def _outside_a_build(monkeypatch):
    for var in ("CATALOG_INCREMENTAL", "CATALOG_BUILD_ID", "CATALOG_BRANCH"):
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# The decorator
# ---------------------------------------------------------------------------

def test_incremental_hands_incremental_handles(client):
    seen = {}

    @incremental(semantic_version=2)
    @transform(src=Input("p.fresh"), log=Output("p.log"))
    def fn(src, log):
        seen.update(src=src, log=log)

    fn(client)
    assert isinstance(seen["src"], IncrementalTransformInput)
    assert isinstance(seen["log"], IncrementalTransformOutput)
    assert seen["log"].semantic_version == 2
    assert fn.incremental == {"semantic_version": 2}
    assert fn.outputs["log"].ref == "p.log"          # the scan contract is untouched


def test_bare_incremental_is_accepted():
    @incremental
    @transform(log=Output("p.log"))
    def fn(log):
        pass

    assert fn.incremental == {"semantic_version": 1}


def test_incremental_below_transform_is_a_type_error():
    with pytest.raises(TypeError, match="above @transform"):
        @transform(log=Output("p.log"))
        @incremental()
        def fn(log):
            pass


def test_incremental_refuses_train():
    with pytest.raises(TypeError, match="@train"):
        @incremental()
        @train(data=Input("p.log"), output=Output("p.model"))
        def fit(data, output):
            pass


def test_foundry_options_are_accepted_and_inert():
    @incremental(snapshot_inputs=["src"], require_incremental=True, allow_retention=True)
    @transform(src=Input("p.fresh"), log=Output("p.log"))
    def fn(src, log):
        pass

    assert fn.incremental == {"semantic_version": 1}


# ---------------------------------------------------------------------------
# Reading "previous"
# ---------------------------------------------------------------------------

def test_previous_is_the_output_before_the_run(client, log_rows):
    @incremental()
    @transform(log=Output("p.log"))
    def fn(log):
        assert log.has_previous
        prev = log.dataframe("previous", schema=["path", "size"])
        pd.testing.assert_frame_equal(prev, log_rows)
        assert log.dataframe("previous") is prev         # memoized

    fn(client)
    assert len(client.of("select")) == 1


def test_previous_restricted_to_columns(client):
    @incremental()
    @transform(log=Output("p.log"))
    def fn(log):
        prev = log.dataframe("previous", columns=["path"])
        assert list(prev.columns) == ["path"]

    fn(client)
    assert '"path"' in client.of("select")[0][1]


def test_previous_of_an_empty_output_is_an_empty_frame_of_the_schema(client):
    @incremental()
    @transform(out=Output("p.fresh"))
    def fn(out):
        assert not out.has_previous
        prev = out.dataframe("previous", schema={"path": "string", "size": "int64"})
        assert prev.empty
        assert list(prev.columns) == ["path", "size"]
        assert str(prev["size"].dtype) == "int64"
        # One "previous" per run: the schema shapes it the first time only.
        assert out.dataframe("previous", ["x"]) is prev

    fn(client)
    assert client.of("select") == []                      # nothing to SELECT from


def test_previous_cannot_be_read_after_the_first_write(client, log_rows):
    @incremental()
    @transform(log=Output("p.log"))
    def fn(log):
        log.write_dataframe(log_rows)
        with pytest.raises(GwenlakeException, match="before the run's first write"):
            log.dataframe("previous")

    fn(client)


def test_previous_read_before_a_write_stays_readable_after(client, log_rows):
    @incremental()
    @transform(log=Output("p.log"))
    def fn(log):
        prev = log.dataframe("previous")
        log.write_dataframe(log_rows)
        assert log.dataframe("previous") is prev

    fn(client)


def test_current_rereads_the_dataset(client):
    @incremental()
    @transform(log=Output("p.log"))
    def fn(log):
        log.dataframe("current")
        log.dataframe("current")

    fn(client)
    assert len(client.of("select")) == 2


def test_unknown_output_mode(client):
    @incremental()
    @transform(log=Output("p.log"))
    def fn(log):
        with pytest.raises(GwenlakeException, match="unknown output mode"):
            log.dataframe("added")

    fn(client)


def test_previous_filesystem_is_a_read_only_view_of_the_files_before(client, log_rows):
    @incremental()
    @transform(log=Output("p.log"))
    def fn(log):
        before = log.filesystem("previous")
        log.write_dataframe(log_rows)
        assert [e["path"] for e in before.ls()] == ["part-old-00000.parquet"]
        assert [e["path"] for e in before.ls(glob="*.parquet")] == ["part-old-00000.parquet"]
        assert before.ls(glob="*.csv") == []
        assert before.read("part-old-00000.parquet") == b"bytes of part-old-00000.parquet"
        assert before.open("part-old-00000.parquet", "rb").read().startswith(b"bytes")
        with pytest.raises(GwenlakeException, match="read-only"):
            before.open("x", "wb")
        with pytest.raises(GwenlakeException, match="read-only"):
            before.write("x", b"")
        with pytest.raises(GwenlakeException, match="not in the output before"):
            before.read("part-new.parquet")
        # The live filesystem sees the run's own write.
        assert len(log.filesystem().ls()) == 2

    fn(client)


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def test_default_write_adds_a_part_file_named_after_the_run(client, log_rows, monkeypatch):
    monkeypatch.setenv("CATALOG_BUILD_ID", "build.a1b2")

    @incremental()
    @transform(log=Output("p.log"))
    def fn(log):
        log.write_dataframe(log_rows)
        log.write_dataframe(log_rows)

    fn(client)
    assert client.of("delete") == []                      # nothing cleared
    assert [c[2:4] for c in client.of("upload")] == [
        ("part-build-a1b2-00000.parquet", None), ("part-build-a1b2-00001.parquet", None),
    ]


def test_default_write_on_iceberg_is_an_append(client, log_rows):
    @incremental()
    @transform(ice=Output("p.ice"))
    def fn(ice):
        ice.write_dataframe(log_rows)

    fn(client)
    assert client.of("upload")[0][3] == "APPEND"


def test_replace_mode_snapshots_once_then_adds(client, log_rows):
    @incremental()
    @transform(log=Output("p.log"), ice=Output("p.ice"))
    def fn(log, ice):
        log.set_mode("replace")
        log.write_dataframe(log_rows)
        log.write_dataframe(log_rows)
        ice.write_dataframe(log_rows, mode="replace")
        ice.write_dataframe(log_rows)

    fn(client)
    assert [c[2] for c in client.of("delete")] == ["part-old-00000.parquet"]
    assert len(client.of("upload")) == 4
    assert [c[3] for c in client.of("upload") if c[1] == "res.dataset.ice"] == ["SNAPSHOT", "APPEND"]
    assert client._datasets["res.dataset.log"].files == [
        c[2] for c in client.of("upload") if c[1] == "res.dataset.log"
    ]


def test_set_mode_after_a_write_is_refused(client, log_rows):
    @incremental()
    @transform(log=Output("p.log"))
    def fn(log):
        log.write_dataframe(log_rows)
        with pytest.raises(GwenlakeException, match="before the run's first write"):
            log.set_mode("replace")
        with pytest.raises(ValueError):
            log.set_mode("overwrite")

    fn(client)


def test_write_dataframes_streams_parts_of_this_run(client, log_rows, monkeypatch):
    monkeypatch.setenv("CATALOG_BUILD_ID", "b1")

    @incremental()
    @transform(log=Output("p.log"))
    def fn(log):
        log.write_dataframes([log_rows, log_rows])

    fn(client)
    assert [c[2] for c in client.of("upload")] == ["part-b1-00-00000.parquet", "part-b1-00-00001.parquet"]


def test_a_vector_output_is_refused(client, log_rows):
    @incremental()
    @transform(vec=Output("p.vec"))
    def fn(vec):
        with pytest.raises(GwenlakeException, match="vector"):
            vec.write_dataframe(log_rows)

    fn(client)


# ---------------------------------------------------------------------------
# Starting over (semantic_version)
# ---------------------------------------------------------------------------

def test_a_bumped_version_starts_over(client, log_rows, monkeypatch):
    monkeypatch.setenv("CATALOG_INCREMENTAL", '{"res.dataset.log": {"semantic_version": 1}}')

    @incremental(semantic_version=2)
    @transform(log=Output("p.log"))
    def fn(log):
        assert log.reset
        assert not log.has_previous
        assert log.dataframe("previous", ["path"]).empty
        log.write_dataframe(log_rows)
        log.write_dataframe(log_rows)

    fn(client)
    assert client.of("select") == []
    assert [c[2] for c in client.of("delete")] == ["part-old-00000.parquet"]   # the first write replaced
    assert len(client.of("upload")) == 2
    assert client.of("empty") == []


def test_the_same_version_continues(client, monkeypatch):
    monkeypatch.setenv("CATALOG_INCREMENTAL", '{"res.dataset.log": {"semantic_version": 2}}')

    @incremental(semantic_version=2)
    @transform(log=Output("p.log"))
    def fn(log):
        assert not log.reset
        assert log.has_previous

    fn(client)


def test_an_unrecorded_output_never_starts_over(client, monkeypatch):
    monkeypatch.setenv("CATALOG_INCREMENTAL", '{"res.dataset.other": {"semantic_version": 1}}')

    @incremental(semantic_version=7)
    @transform(log=Output("p.log"))
    def fn(log):
        assert not log.reset

    fn(client)


def test_starting_over_with_nothing_to_write_still_empties_the_output(client, monkeypatch):
    monkeypatch.setenv("CATALOG_INCREMENTAL", '{"res.dataset.log": {"semantic_version": 1}}')
    monkeypatch.setenv("CATALOG_BRANCH", "exp")

    @incremental(semantic_version=2)
    @transform(log=Output("p.log"))
    def fn(log):
        return None

    fn(client)
    assert client.of("empty") == [("empty", "res.dataset.log", "exp")]


# ---------------------------------------------------------------------------
# transform_df and the inputs
# ---------------------------------------------------------------------------

def test_transform_df_appends_what_the_body_returns(client, log_rows):
    @incremental()
    @transform_df(src=Input("p.log"), out=Output("p.fresh"))
    def fn(src):
        assert isinstance(src, pd.DataFrame)              # whole, as a DataFrame
        return src.head(1)

    fn(client)
    assert client.of("delete") == []
    assert len(client.of("upload")) == 1


def test_transform_df_body_may_touch_its_output_handle_first(client, log_rows):
    @incremental()
    @transform_df(src=Input("p.fresh"), log=Output("p.log"))
    def fn(src, log):
        assert set(log.dataframe("previous")["path"]) == {"a.pdf", "b.pdf"}
        log.set_mode("replace")
        return log_rows

    fn(client)
    assert [c[2] for c in client.of("delete")] == ["part-old-00000.parquet"]
    assert len(client.of("upload")) == 1


def test_transform_df_several_outputs(client, log_rows):
    @incremental()
    @transform_df(src=Input("p.fresh"), a=Output("p.log"), b=Output("p.ice"))
    def fn(src):
        return {"a": log_rows, "b": log_rows}

    fn(client)
    assert sorted((c[1], c[3]) for c in client.of("upload")) == [
        ("res.dataset.ice", "APPEND"), ("res.dataset.log", None),
    ]


def test_input_modes_added_and_previous_are_refused(client):
    @incremental()
    @transform(src=Input("p.log"), log=Output("p.fresh"))
    def fn(src, log):
        assert len(src.dataframe()) == 2
        assert len(src.dataframe("current")) == 2
        for mode in ("added", "previous"):
            with pytest.raises(GwenlakeException, match="snapshot input"):
                src.dataframe(mode)
        with pytest.raises(GwenlakeException, match="snapshot input"):
            src.filesystem("added")
        with pytest.raises(GwenlakeException, match="unknown input mode"):
            src.dataframe("latest")

    fn(client)


# ---------------------------------------------------------------------------
# Without @incremental nothing moved
# ---------------------------------------------------------------------------

def test_plain_transform_still_replaces(client, log_rows):
    @transform(log=Output("p.log"))
    def fn(log):
        assert not hasattr(log, "set_mode")
        log.write_dataframe(log_rows)

    fn(client)
    assert [c[2] for c in client.of("delete")] == ["part-old-00000.parquet"]
    assert [c[2] for c in client.of("upload")] == ["data.parquet"]


def test_filesystem_calls_carry_the_build_branch(client, log_rows, monkeypatch):
    monkeypatch.setenv("CATALOG_BRANCH", "exp")

    @transform(log=Output("p.log"))
    def fn(log):
        log.filesystem().ls()
        log.filesystem().read("part-old-00000.parquet")
        log.write_dataframe(log_rows)

    fn(client)
    assert client.of("list")[0][3] == "exp"
    assert client.of("download")[0][3] == "exp"
    assert client.of("delete")[0][3] == "exp"
