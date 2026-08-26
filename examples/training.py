"""Training on the GPU pool, where a run is interrupted and picks itself up.

Same bindings as ``transforms.train``; the difference is the ``run``, which
carries resumption, eviction and tracking. Run it locally with no GPU and no
tracking server -- it degrades to a plain loop:

    uv run python examples/training.py

Then interrupt it with Ctrl-C partway through and start it again: it resumes
where it stopped, because that is the behaviour the pool depends on.
"""

import random
import time

import gwenlake
from gwenlake.training import train, Input, Output

client = gwenlake.Gwenlake() if gwenlake.Credentials().is_configured else None


def batches(source, size=32):
    """Whatever streams your data. On the pool this reads from the volume the
    platform mounts; here it is noise, so the example runs anywhere."""
    while True:
        yield [random.random() for _ in range(size)]


@train(
    training_set=Input("Project_A.training_set"),
    output=Output("Project_A.my_model"),
    steps=200,
    eval_every=50,
)
def fit(training_set, output, run):
    weight, loss = 0.5, 1.0

    # A previous life may have left state here. `run.resumed` is the only
    # thing to test; the directory is the same one either way.
    if run.resumed:
        weight = float((run.resume_path / "weight.txt").read_text())
        print(f"resumed at step {run.start_step} with weight {weight:.4f}")

    for step, batch in run.steps(batches(training_set)):
        time.sleep(0.02)        # stands in for a real step, and makes the
                                # run long enough to interrupt by hand
        loss = loss * 0.98 + random.uniform(-0.01, 0.01)
        weight += 0.001
        run.log({"loss": loss})

        if run.at_eval:
            # Written AND shipped here rather than at the end: an evicted run
            # never reaches the end, and the volume is node-local.
            with run.checkpoint() as ck:
                ck.path("weight.txt").write_text(str(weight))
                ck.metrics = {"accuracy": 1 - loss}
            print(f"step {step}/{run.total_steps} · loss {loss:.4f}")

    # Returning nothing would store run.summary() instead.
    return {"accuracy": 1 - loss, "final_weight": weight}


if __name__ == "__main__":
    print(fit(client))
