"""Training that survives being interrupted.

``transforms.train`` already produces a model from datasets, and its
ergonomics are the ones used here. What it cannot express is a run that is
*long*: a build reads its inputs into memory, runs to completion, and writes
its output. A training on a shared GPU does none of those things — the data
does not fit, the run lasts hours, and it is evicted whenever inference needs
the card.

So this module keeps the binding style and adds the one object that
difference requires: a :class:`Run`, which owns the four things that are easy
to get wrong and expensive to get wrong.

    from gwenlake.training import train, Input, Output

    @train(
        training_set=Input("cyim.bcmc-train"),
        output=Output("cyim.bcmc"),
        steps=30000, eval_every=1000,
    )
    def fit(training_set, output, run):
        model, opt = build()
        if run.resumed:                      # a previous life left state here
            load(model, opt, run.resume_path)

        for step, batch in run.steps(batches(training_set)):
            run.log({"loss": train_step(model, opt, batch)})
            if run.at_eval:
                with run.checkpoint() as ck:
                    save(model, opt, ck.path("state.safetensors"))
                    ck.metrics = evaluate(model)

        return run.summary()

**What the Run owns, and why each one is here.** Every item below was a real
failure before it was a feature:

- *Eviction.* SIGTERM is caught and turned into an ordinary end of loop, so
  the run stops between two steps rather than mid-optimiser. The handler is
  installed even though the process is PID 1 in a container -- where Linux
  delivers **no** signal whose disposition is the default, and Python
  installs one for SIGINT only. Without it the pod is SIGKILLed at the end of
  its grace period and everything since the last checkpoint is lost.
- *Resumption.* Checkpoints live in a directory keyed to the run, and the
  step they carry is what `steps()` fast-forwards to. A restarted pod picks
  the run back up instead of starting it over.
- *Tracking.* The tracking run id is written next to the checkpoints, not
  held in memory, so a restart reports into the SAME run. Otherwise every
  eviction opens a new one and the curve comes back cut into pieces.
- *Durability.* Checkpoints are uploaded as they are written, not at the end:
  a run that is evicted never reaches the end, and the volume it writes to is
  usually a disk on one node.

Tracking degrades to a no-op when it is unreachable. A metrics outage must
never take a training down with it.
"""

from __future__ import annotations

import json
import os
import signal
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import (Any, Callable, Dict, Iterable, Iterator, Optional,
                    TYPE_CHECKING, Tuple)

if TYPE_CHECKING:
    from .transforms import Input, Model, Output


def _bindings():
    from .transforms import (Input, Model, Output, TransformInput,
                             TransformModel, _split_bindings)
    return Input, Model, Output, TransformInput, TransformModel, _split_bindings

__all__ = ["train", "entrypoint", "discover", "Run", "Tracker",
           "Preemption", "Input", "Output", "Model"]

STATE_FILE = "run-state.json"
RUN_ID_FILE = "mlflow-run-id"
ENV_FILE = ".env"
#: The tracking server belongs to the project, not to each workstation's
#: setup. MLFLOW_TRACKING_URI still wins when it is set.
TRACKING_URI = "https://api.gwenlake.com/v1/mlflow"
#: Credentials that make a remote server usable. Without one of them the
#: tracker stays inert rather than opening a run that would be refused at
#: the first call.
CREDENTIAL_VARS = ("MLFLOW_TRACKING_TOKEN", "MLFLOW_TRACKING_PASSWORD",
                   "MLFLOW_TRACKING_AWS_SIGV4", "MLFLOW_TRACKING_AUTH")
#: Where a run keeps its checkpoints. The platform points this at a volume
#: that outlives the pod; a laptop run gets a local directory.
WORK_DIR_ENV = "GWENLAKE_RUN_DIR"
#: Set by the platform to the name of the function to run, as the catalog
#: build engine does with CATALOG_FUNCTION.
FUNCTION_ENV = "GWENLAKE_TRAIN_FUNCTION"


def __getattr__(name: str) -> Any:
    """Resolve the catalog names lazily.

    They are re-exported for convenience -- `from gwenlake.training import
    train, Input, Output` reads well -- but resolving them at import time
    would drag pandas and pydantic into every training container. This makes
    them cost nothing until someone actually names one.
    """
    if name in ("Input", "Output", "Model"):
        from . import transforms
        return getattr(transforms, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def load_env() -> None:
    """Read the nearest `.env` into the environment.

    Ten lines rather than a dependency: what is wanted is one token, and the
    file is ours. A variable ALREADY in the environment is never overwritten
    -- the platform passes its own secret and must keep winning over
    whatever a checkout happens to contain.
    """
    for start in (Path.cwd().resolve(), Path(__file__).resolve().parent):
        for base in (start, *start.parents):
            path = base / ENV_FILE
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip("\'\"")
                if key and key not in os.environ:
                    os.environ[key] = value
            return


def tracking_uri() -> str:
    return os.environ.get("MLFLOW_TRACKING_URI") or TRACKING_URI


def experiment_name(explicit: Optional[str] = None) -> str:
    return (explicit or os.environ.get("MLFLOW_EXPERIMENT_NAME")
            or os.environ.get("MLFLOW_EXPERIMENT") or "default")


def run_name(model: str, explicit: Optional[str] = None,
             experiment: Optional[str] = None) -> str:
    """`attn`, `knn`, ... plus what tells two runs of the same model apart.

    The platform names its Job after the project, the commit and the CI job,
    and passes it as GWENLAKE_RUN_NAME. A leading project name is dropped:
    the experiment already says which project this is, and repeating it
    makes every run in the list start with the same word.
    """
    if explicit:
        return explicit
    suffix = (os.environ.get("GWENLAKE_RUN_NAME")
              or os.environ.get("RUN_ID") or "").strip()
    exp = (experiment or "").lower()
    if exp and suffix.lower().startswith(exp + "-"):
        suffix = suffix[len(exp) + 1:]
    return f"{model}-{suffix or datetime.now().strftime('%Y%m%d-%H%M')}"


class Preemption:
    """Turns SIGTERM into a flag the loop reads where it chooses.

    Usable on its own, for a training loop that already owns its step
    accounting and its checkpoints -- :class:`Run` holds one of these.

        preemption = Preemption()
        for step in ...:
            ...
            if preemption.requested:      # after a checkpoint, never mid-step
                sys.exit(143)

    Two details make the naive version fail. `exec`'d as a container
    entrypoint the process is PID 1, and Linux delivers **no** signal to PID 1
    whose disposition is the default; Python installs a handler for SIGINT
    only, so SIGTERM was silently discarded and the pod was SIGKILLed at the
    end of its grace period. And a handler must not checkpoint itself: it
    runs between bytecode instructions, possibly mid-optimiser-step, and the
    frameworks underneath are not reentrant. So it raises a flag, nothing
    more.
    """

    def __init__(self, quiet: bool = False):
        self.requested = False
        self._quiet = quiet
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, self._catch)
            except ValueError:
                pass        # not the main thread: nothing to install

    def _catch(self, signum, _frame) -> None:
        self.requested = True
        if not self._quiet:
            print(f"gwenlake: {signal.Signals(signum).name} received, "
                  f"stopping at the next safe point", flush=True)


class _Checkpoint:
    """The handle yielded by :meth:`Run.checkpoint`."""

    def __init__(self, run: "Run", step: int):
        self._run, self.step = run, step
        self.metrics: Dict[str, float] = {}
        self.written: list[Path] = []

    def path(self, name: str) -> Path:
        """A path to write to, inside this run's directory."""
        p = self._run.dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        self.written.append(p)
        return p


class Run:
    """The state a training carries across its own interruptions."""

    def __init__(self, name: str, params: Dict[str, Any], *,
                 steps: Optional[int] = None, epochs: Optional[int] = None,
                 eval_every: int = 1000, work_dir: Optional[Path] = None,
                 experiment: Optional[str] = None, model: str = "model",
                 tracking: bool = True, start_step: Optional[int] = None):
        self.name = name
        #: A step budget, an epoch budget, or neither -- then the source
        #: decides when it is done. Steps are what a resume counts in;
        #: epochs are what you usually mean.
        self.total_steps = steps
        self.total_epochs = epochs
        self.epoch = 0
        self.eval_every = eval_every
        self.dir = Path(work_dir or os.environ.get(WORK_DIR_ENV) or f"./runs/{name}")
        self.dir.mkdir(parents=True, exist_ok=True)

        self.step = 0
        self.at_eval = False
        self._preemption = Preemption(quiet=True)
        self._started = time.monotonic()
        self._best: Dict[str, float] = {}

        state = self._read_state()
        # The step of the last CHECKPOINT -- see `steps()` for why this is
        # not the last step executed.
        #
        # `start_step` lets a project that already reads the step from its
        # own checkpoints keep that as the single source of truth. Two
        # sources disagreeing means loading weights from one step and
        # resuming the loop at another, silently dropping the difference.
        self.start_step: int = (start_step if start_step is not None
                                else state.get("step", 0))
        #: True when a previous life left checkpoints here.
        self.resumed: bool = self.start_step > 0
        #: The directory to load from -- the same one, which is the point.
        self.resume_path: Path = self.dir

        self._tracker = Tracker(self.dir, params, model=model, name=name,
                                 experiment=experiment, enabled=tracking)

    @property
    def preempted(self) -> bool:
        """True once eviction has been asked for."""
        return self._preemption.requested

    # -------------------------------------------------------------- state --
    def _read_state(self) -> Dict[str, Any]:
        p = self.dir / STATE_FILE
        if not p.is_file():
            return {}
        try:
            return json.loads(p.read_text())
        except (OSError, ValueError):
            # A truncated state file means the last write was interrupted.
            # Starting over beats crashing on someone else's half-written JSON.
            return {}

    def _write_state(self, **fields: Any) -> None:
        p = self.dir / STATE_FILE
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({**self._read_state(), **fields}, indent=2))
        tmp.replace(p)      # atomic: a crash mid-write cannot corrupt it

    # --------------------------------------------------------------- loop --
    def steps(self, batches: Any) -> Iterator[Tuple[int, Any]]:
        """Yield ``(step, batch)``, resuming and stopping on eviction.

        `batches` is an iterable, or -- when the run is measured in EPOCHS --
        a callable returning a fresh one. A step is the unit that survives an
        eviction, so it is what resumption counts in; an epoch is the unit
        you actually mean, so it is what you declare. Both, in their place.

        Fast-forwards over the batches a previous life already consumed,
        across epoch boundaries, so the caller's loop reads the same whether
        it is a first run or the fourth restart.
        """
        if self.total_steps and self.start_step >= self.total_steps:
            # Doing nothing quietly is the worst of the three outcomes here:
            # the caller asked for fewer steps than a previous life already
            # ran, and would otherwise get a green run that trained nothing.
            print(f"gwenlake: already at step {self.start_step} and steps is "
                  f"{self.total_steps} -- nothing to do. Raise steps to train "
                  f"further, or point the run at a fresh directory.",
                  flush=True)
            return

        if self.total_epochs and not callable(batches):
            raise TypeError(
                "a run measured in epochs needs a callable returning a fresh "
                "iterable (e.g. `run.steps(lambda: batches(data))`): an "
                "exhausted iterator cannot be walked a second time")

        step = self.start_step
        skipping = self.start_step
        epoch = 0
        while True:
            epoch += 1
            if self.total_epochs and epoch > self.total_epochs:
                break
            self.epoch = epoch
            it = iter(batches() if callable(batches) else batches)

            exhausted = True
            for batch in it:
                exhausted = False
                # Fast-forward what a previous life already consumed. Counted
                # across epochs, so a resume lands in the right pass.
                if skipping:
                    skipping -= 1
                    continue
                step += 1
                self.step = step
                self.at_eval = (step % self.eval_every == 0
                                or step == self.total_steps)
                yield step, batch
                if self._preemption.requested:
                    # Deliberately NOT recording `step` here. The resume point
                    # is the last CHECKPOINT, not the last step executed: the
                    # two differ by up to eval_every, and resuming at the loop
                    # position while loading older weights would silently drop
                    # every update in between.
                    self._write_state(preempted=True)
                    self._tracker.close(status="KILLED")
                    return
                if self.total_steps and step >= self.total_steps:
                    self._write_state(step=step, preempted=False)
                    return

            if exhausted:
                # An empty source would otherwise spin forever on epochs.
                break
            if not self.total_epochs:
                # No epoch budget: the source decides when it is done.
                break

        self._write_state(step=step, preempted=False)

    # ------------------------------------------------------------ tracking --
    def log(self, metrics: Dict[str, float]) -> None:
        """Record metrics against the current step."""
        self._tracker.log(metrics, self.step)

    @contextmanager
    def checkpoint(self) -> Iterator[_Checkpoint]:
        """Write a checkpoint, and ship it.

        Uploads on exit rather than at the end of training: a run that is
        evicted never reaches the end, and the directory written to is
        usually node-local.
        """
        ck = _Checkpoint(self, self.step)
        yield ck
        if ck.metrics:
            self.log(ck.metrics)
            self._best = {k: max(v, self._best.get(k, v)) for k, v in ck.metrics.items()}
        self._write_state(step=ck.step, metrics=ck.metrics)
        for p in ck.written:
            self._tracker.artifact(p)

    def summary(self) -> Dict[str, Any]:
        """What the decorator stores on the model as its metrics."""
        return {**self._best,
                "steps": self.step,
                "elapsed_s": round(time.monotonic() - self._started, 1),
                "preempted": self._preemption.requested}


class Tracker:
    """MLflow, optional and inert when it cannot be reached."""

    def __init__(self, out: Path, params: Dict[str, Any], *, model: str,
                 name: Optional[str], experiment: Optional[str],
                 enabled: bool = True):
        self.enabled, self._mlflow = False, None
        if not enabled or os.environ.get("MLFLOW_DISABLE"):
            return
        load_env()
        uri = tracking_uri()
        # A local file:// or a hand-started server needs no credential; a
        # remote one does, and running without one is a run refused at the
        # first call rather than a trace.
        if uri.startswith("http") and not any(os.environ.get(v)
                                              for v in CREDENTIAL_VARS):
            print(f"gwenlake: no {CREDENTIAL_VARS[0]} in the environment or "
                  f"in {ENV_FILE}: tracking off", flush=True)
            return
        try:
            import mlflow
        except ImportError:
            print("gwenlake: mlflow not installed, tracking off "
                  "(pip install 'mlflow-skinny[extras]')", flush=True)
            return
        try:
            # A tracking server that hangs must not hold a GPU hostage.
            os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "20")
            os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "3")
            mlflow.set_tracking_uri(uri)
            exp = experiment_name(experiment)
            mlflow.set_experiment(exp)
            # The run id lives on disk beside the checkpoints, not in memory:
            # that is what survives an eviction.
            marker = Path(out) / RUN_ID_FILE
            run_id = marker.read_text().strip() if marker.is_file() else None
            run = mlflow.start_run(run_id=run_id,
                                   run_name=run_name(model, name, exp))
            if run_id is None:
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text(run.info.run_id)
                mlflow.log_params(params)
            self._mlflow, self.enabled = mlflow, True
            print(f"gwenlake: {uri} · experiment {exp} · run "
                  f"{run.info.run_name} ({run.info.run_id})"
                  f"{' resumed' if run_id else ''}", flush=True)
        except Exception as e:                              # noqa: BLE001
            print(f"gwenlake: tracking off ({e.__class__.__name__}: {e})",
                  flush=True)

    def log(self, metrics: Dict[str, float], step: int) -> None:
        if not self.enabled:
            return
        try:
            self._mlflow.log_metrics({k: float(v) for k, v in metrics.items()},
                                     step=step)
        except Exception:                                   # noqa: BLE001
            pass        # a lost metric is no reason to stop a training

    def artifact(self, path: Path) -> None:
        if not self.enabled or not Path(path).is_file():
            return
        try:
            self._mlflow.log_artifact(str(path))
        except Exception:                                   # noqa: BLE001
            pass

    def close(self, status: str = "FINISHED") -> None:
        if not self.enabled:
            return
        try:
            self._mlflow.end_run(status=status)
        except Exception:                                   # noqa: BLE001
            pass


def train(*, steps: Optional[int] = None, epochs: Optional[int] = None,
          eval_every: int = 1000,
          model: str = "model", experiment: Optional[str] = None,
          run_name: Optional[str] = None, tracking: bool = True,
          params: Optional[Dict[str, Any]] = None,
          **bindings: Any) -> Callable:
    """Decorate a function that trains a model on the GPU pool.

    Catalog bindings are optional. Without them the decorated function
    receives only ``run``, which is the shape a project whose data the
    platform mounts will want; with them it also receives its ``Input`` and
    ``Output``, and the returned metrics land on the model.

    ``params`` carries the hyperparameters worth recording alongside the
    run -- everything the tracker should show next to its metrics.

    ``start_step`` may be passed at call time by a project that reads the
    resume point from its own checkpoints -- then that is the only source of
    truth, and the library does not compete with it.

    ``model`` names the thing being trained (``attn``, ``knn``, ...): runs
    are named after it, so two heads on the same data stay apart in the
    experiment. ``tracking=False`` runs without touching the tracking
    server. Both are overridable per call, which is what a ``--no-mlflow``
    flag ends up doing.

    Bindings work as in ``transforms.train`` -- ``Input`` arrives as a
    :class:`TransformInput` (not a DataFrame: a training set is streamed, not
    loaded), ``Output`` and ``Model`` as :class:`TransformModel`. The function
    additionally receives ``run``, and what it returns is stored as the
    model's metrics; returning nothing stores :meth:`Run.summary` instead.
    """
    # Catalog bindings are OPTIONAL here, unlike in transforms.train. A
    # training on the pool reads what the platform mounts and ships its
    # artifacts to the tracking server; requiring an Output would exclude
    # every project whose data is not in the catalog, which is most of them
    # to begin with.
    if bindings:
        _, _, _, TransformInput, TransformModel, _split = _bindings()
        inputs, outputs, models = _split(bindings)
        if len(outputs) > 1:
            raise TypeError(
                f"train takes at most one Output (the model), got {len(outputs)}")
    else:
        TransformInput = TransformModel = None
        inputs, outputs, models = {}, {}, {}

    def decorator(fn: Callable) -> Callable:
        import functools
        import inspect
        # `signature` here, not `params`: `params` is the decorator's own
        # argument, and shadowing it silently dropped every hyperparameter a
        # caller passed -- a run recorded four parameters instead of
        # thirteen, with nothing to say so.
        signature = inspect.signature(fn).parameters
        if "run" not in signature:
            raise TypeError(
                f"{fn.__name__} must accept a 'run' parameter -- it carries "
                "resumption, eviction and tracking")

        @functools.wraps(fn)
        def wrapper(client: Any, **overrides: Any) -> Any:
            run = Run(name=run_name,
                      params={"steps": steps, "epochs": epochs,
                              "eval_every": eval_every,
                              "model": model, **(params or {}),
                              **{k: str(v.ref) for k, v in bindings.items()}},
                      steps=overrides.pop("steps", steps),
                      epochs=overrides.pop("epochs", epochs),
                      eval_every=overrides.pop("eval_every", eval_every),
                      experiment=experiment, model=model,
                      start_step=overrides.pop("start_step", None),
                      # A run that must not touch the tracking server: the
                      # `--no-mlflow` of a command line, as a parameter.
                      tracking=overrides.pop("tracking", tracking))
            if bindings and client is None:
                # Otherwise the failure surfaces deep inside the catalog
                # client as `'NoneType' has no attribute 'statements'`,
                # which says nothing about what is actually missing.
                raise RuntimeError(
                    f"{fn.__name__} binds catalog datasets "
                    f"({', '.join(sorted(bindings))}) but no client was "
                    f"given: check ~/.gwenlake/credentials or "
                    f"GWENLAKE_API_KEY")

            call: Dict[str, Any] = {"run": run}
            for name in signature:
                if name in inputs:
                    call[name] = TransformInput(client, inputs[name].ref)
                elif name in models or name in outputs:
                    ref = (models.get(name) or outputs[name]).ref
                    call[name] = TransformModel(client, ref)
            try:
                result = fn(**call)
            finally:
                run._tracker.close("KILLED" if run.preempted else "FINISHED")
            metrics = result if isinstance(result, dict) else run.summary()
            if client is not None and outputs:
                try:
                    TransformModel(client, next(iter(outputs.values())).ref).update(
                        metrics=metrics)
                except Exception as e:                      # noqa: BLE001
                    # Outside a build the model endpoints are not reachable.
                    # Said out loud rather than swallowed: the training did
                    # happen and its metrics are in the tracker, but the
                    # model card was not updated and that is worth knowing.
                    print(f"gwenlake: model metrics not stored "
                          f"({e.__class__.__name__}: {e})", flush=True)
            return metrics

        wrapper.inputs, wrapper.outputs, wrapper.models = inputs, outputs, models
        wrapper.is_training = True
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

FUNCTION_ENV = "GWENLAKE_TRAIN_FUNCTION"
#: Where to look. A project's code is under src/ or at the root; nothing else
#: is worth importing, and importing a virtualenv would be a disaster.
_SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", "build",
         "dist", "tests", "test", ".tox", ".mypy_cache", "site-packages"}


def _module_name(base: Path, path: Path) -> tuple[str, str | None]:
    """The dotted name a file should be imported under, and the root to add.

    Importing a file under an invented name (``_gwenlake_scan_1234``) gives it
    no parent package, so **every relative import inside it fails** --
    ``attempted relative import with no known parent package``. A project laid
    out as a package, which is what any real one looks like, is then skipped
    module by module, and the training function is never found.

    Walking up while ``__init__.py`` exists recovers the real name: a file at
    ``src/pkg/sub/mod.py`` under a package is imported as ``pkg.sub.mod``, with
    ``src`` added to ``sys.path`` so its siblings resolve. A loose script keeps
    a scan-local name -- it has no package, so there is nothing to recover.
    """
    parts = [path.stem] if path.name != "__init__.py" else []
    parent = path.parent
    while (parent / "__init__.py").exists() and parent != base.parent:
        parts.insert(0, parent.name)
        parent = parent.parent
    if not parts:
        return f"_gwenlake_scan_{abs(hash(str(path)))}", None
    if len(parts) == 1 and path.name != "__init__.py":
        # Not inside a package: no relative import to satisfy, and a bare
        # module name could collide with an installed one.
        return f"_gwenlake_scan_{abs(hash(str(path)))}", None
    return ".".join(parts), str(parent)


def discover(root: str | Path = ".") -> Dict[str, Callable]:
    """Every ``@train``-decorated function in a project, by name.

    Imports each candidate module, which is the only way to see a decorator:
    it exists at import time, not in the source text. Modules that fail to
    import are reported and skipped rather than aborting the search -- one
    broken file must not hide the function you asked for.

    This is what lets the platform run a project without being told where its
    training lives: `gwenlake train` finds it.
    """
    import importlib.util
    import sys

    root = Path(root).resolve()
    found: Dict[str, Callable] = {}
    # Only src/ when it exists. Scanning the root as well imports whatever
    # sits beside the code -- a data generator, a notebook helper -- and
    # importing a script RUNS it. One such script wrote its output to a
    # directory named after a command-line flag before this was fixed.
    roots = [root / "src"] if (root / "src").is_dir() else [root]

    for base in roots:
        for path in sorted(base.rglob("*.py")):
            if any(part in _SKIP or part.startswith(".") for part in path.parts):
                continue
            if path.name.startswith("_") and path.name != "__init__.py":
                continue
            name, extra_path = _module_name(base, path)
            try:
                spec = importlib.util.spec_from_file_location(
                    name, path,
                    submodule_search_locations=[str(path.parent)]
                    if path.name == "__init__.py" else None,
                )
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                # The package's own root on `sys.path`, so a module reached by
                # its dotted name can import its siblings.
                if extra_path and extra_path not in sys.path:
                    sys.path.insert(0, extra_path)
                spec.loader.exec_module(module)
            except Exception as e:                          # noqa: BLE001
                # A module that will not import is not necessarily the one
                # being looked for -- say so and keep going.
                print(f"gwenlake: skipped {path.relative_to(root)} "
                      f"({e.__class__.__name__}: {e})", flush=True)
                continue
            for attr in vars(module).values():
                if callable(attr) and getattr(attr, "is_training", False):
                    found.setdefault(attr.__name__, attr)
    return found


def entrypoint(root: str | Path = ".", client: Any = None,
               function: Optional[str] = None, **overrides: Any) -> Any:
    """Find the training this run is for, and run it.

    The name comes from ``function``, else ``GWENLAKE_TRAIN_FUNCTION``. With
    neither, a project holding exactly one training runs it; a project
    holding several is asked which, rather than picking one -- running the
    wrong training for an hour is worse than an error.
    """
    found = discover(root)
    if not found:
        raise RuntimeError(
            f"no @train-decorated function under {Path(root).resolve()}")

    wanted = (function or os.environ.get(FUNCTION_ENV) or "").strip()
    if wanted:
        if wanted not in found:
            raise RuntimeError(
                f"{FUNCTION_ENV}={wanted!r} matches nothing "
                f"(have: {', '.join(sorted(found))})")
        chosen = found[wanted]
    elif len(found) == 1:
        chosen = next(iter(found.values()))
    else:
        raise RuntimeError(
            f"{len(found)} trainings here ({', '.join(sorted(found))}); "
            f"set {FUNCTION_ENV} to say which")

    print(f"gwenlake: running {chosen.__name__}", flush=True)
    return chosen(client, **overrides)


def _cli() -> None:
    """`gwenlake-train` -- one command for every project on the pool.

    Deliberately not a subcommand of `gwenlake`: that group builds an
    authenticated client on every invocation, and a training whose data the
    platform mounts has no catalog to talk to. Requiring credentials to run
    it would be requiring them for nothing.
    """
    import argparse

    p = argparse.ArgumentParser(
        prog="gwenlake-train",
        description="Find this project's @train-decorated training and run it.")
    p.add_argument("--path", default=".", help="project root to search")
    p.add_argument("--function", default=None,
                   help="which training, when the project holds several")
    p.add_argument("--steps", type=int, default=None)
    p.add_argument("--eval-every", type=int, default=None)
    p.add_argument("--list", action="store_true",
                   help="show what was found and stop")
    args = p.parse_args()

    if args.list:
        for name in sorted(discover(args.path)):
            print(name)
        return

    overrides = {k: v for k, v in (("steps", args.steps),
                                   ("eval_every", args.eval_every))
                 if v is not None}

    # Built when it can be, passed as None when it cannot. A training whose
    # data the platform mounts needs no catalog and must not be blocked by
    # missing credentials; one that binds an Input does, and says so itself.
    try:
        from . import Gwenlake
        client = Gwenlake()
    except Exception:                                       # noqa: BLE001
        client = None

    entrypoint(args.path, client=client, function=args.function, **overrides)
