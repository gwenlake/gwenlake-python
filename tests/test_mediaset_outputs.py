"""An ``Output`` naming a mediaset: the files a transform writes.

The handle a body receives for it writes through the mediasets API
(``upload`` into the right directory), lists and reads back, refuses rows,
and keeps no incremental log; the dataset outputs beside it are untouched.
A build whose target is the mediaset selects the transform that writes it.
"""

import pandas as pd
import pytest

from gwenlake.exceptions import GwenlakeException
from gwenlake.transforms import (
    IncrementalTransformOutput,
    Output,
    TransformMediasetOutput,
    TransformOutput,
    _selected_transforms,
    incremental,
    transform,
)


class FakeClient:
    """One project ``p`` with a dataset ``log`` and an image mediaset ``images``."""

    def __init__(self):
        self.uploads = {}
        client = self

        class Projects:
            def list(self_):
                return [{"id": "res.project.p", "alias": "p"}]

        class Datasets:
            def list(self_, project_id=None, **_):
                return [{"id": "res.dataset.log", "alias": "log"}]

            def get(self_, dataset_id):
                return {"id": dataset_id, "type": "iceberg"}

        class Mediasets:
            def list(self_, project_id=None, **_):
                return [{"id": "res.mediaset.images", "alias": "images", "slug": "images"}]

            def upload(self_, mediaset_id, data, path=None, filename=None):
                key = f"{path}/{filename}" if path else filename
                client.uploads[(mediaset_id, key)] = data
                return {"filename": filename, "path": path, "file_size": len(data), "uploaded": True}

            def list_files(self_, mediaset_id, path=None):
                prefix = f"{path.rstrip('/')}/" if path else ""
                names = set()
                for (_, key) in client.uploads:
                    if key.startswith(prefix):
                        rest = key[len(prefix):]
                        names.add(rest.split("/", 1)[0] + ("/" if "/" in rest else ""))
                return [{"filename": n, "file_size": None if n.endswith("/") else 1} for n in sorted(names)]

            def download(self_, mediaset_id, filepath):
                return client.uploads[(mediaset_id, filepath)]

            def delete_file(self_, mediaset_id, filepath):
                return client.uploads.pop((mediaset_id, filepath), None) is not None

        self.projects, self.datasets, self.mediasets = Projects(), Datasets(), Mediasets()


def test_an_output_naming_a_mediaset_gets_a_mediaset_handle():
    client = FakeClient()
    seen = {}

    @transform(log=Output("p.log"), images=Output("p.images"))
    def render(log, images):
        seen["log"], seen["images"] = log, images
        images.filesystem().write("2026/11/05/scene/quicklook.png", b"png")
        images.write("2026/11/05/scene/r0_c0.png", b"tile")

    render(client)
    assert isinstance(seen["log"], TransformOutput) and seen["log"].dataset_id == "res.dataset.log"
    assert isinstance(seen["images"], TransformMediasetOutput) and seen["images"].mediaset_id == "res.mediaset.images"
    assert client.uploads == {
        ("res.mediaset.images", "2026/11/05/scene/quicklook.png"): b"png",
        ("res.mediaset.images", "2026/11/05/scene/r0_c0.png"): b"tile",
    }


def test_a_mediaset_output_lists_reads_and_refuses_rows():
    client = FakeClient()
    out = TransformMediasetOutput(client, "p.images")
    fs = out.filesystem()
    fs.write("a/b/one.png", b"1")
    fs.write("a/two.png", b"2")
    with fs.open("a/c/three.png", "wb") as f:
        f.write(b"3")
    assert [e["path"] for e in fs.ls("a")] == ["a/b", "a/c", "a/two.png"]
    assert sorted(e["path"] for e in fs.ls(glob="**/*.png")) == ["a/b/one.png", "a/c/three.png", "a/two.png"]
    assert fs.read("a/b/one.png") == b"1" and fs.open("a/two.png").read() == b"2"
    assert fs.delete("a/two.png") and ("res.mediaset.images", "a/two.png") not in client.uploads
    with pytest.raises(GwenlakeException, match="holds files, not rows"):
        out.write_dataframe(pd.DataFrame({"x": [1]}))
    with pytest.raises(GwenlakeException, match="no previous state"):
        out.filesystem("previous")


def test_under_incremental_the_mediaset_keeps_no_log_and_the_dataset_stays_incremental():
    client = FakeClient()
    seen = {}

    @incremental(semantic_version=1)
    @transform(log=Output("p.log"), images=Output("res.mediaset.images"))
    def render(log, images):
        seen["log"], seen["images"] = log, images
        images.write("x.png", b"x")

    render(client)
    assert isinstance(seen["log"], IncrementalTransformOutput)
    assert isinstance(seen["images"], TransformMediasetOutput)
    assert client.uploads == {("res.mediaset.images", "x.png"): b"x"}


def test_a_build_targeting_the_mediaset_selects_its_writer(monkeypatch):
    client = FakeClient()

    @transform(images=Output("p.images"))
    def render(images):
        ...

    @transform(log=Output("p.log"))
    def summarise(log):
        ...

    monkeypatch.delenv("CATALOG_FUNCTION", raising=False)
    monkeypatch.setenv("CATALOG_OUTPUT_ID", "res.mediaset.images")
    assert _selected_transforms(client, (render, summarise)) == [render]
    monkeypatch.delenv("CATALOG_OUTPUT_ID")
    monkeypatch.setenv("CATALOG_OUTPUT", "s3://b/gwenlake/mediasets/res.mediaset.images/files/")
    assert _selected_transforms(client, (render, summarise)) == [render]
    monkeypatch.setenv("CATALOG_OUTPUT", "s3://b/gwenlake/datasets/res.dataset.log/files/")
    assert _selected_transforms(client, (render, summarise)) == [summarise]
