"""Training on the GPU pool: a run that is interrupted and picks itself up.

Run it here, with no GPU, no cluster and no tracking server -- it degrades to
a plain loop:

    uv run python examples/training.py

Then interrupt it with Ctrl-C partway through and start it again. It resumes
from its last checkpoint, which is not a nicety: on the pool, inference
preempts training whenever it needs the card, and a run that could not resume
would lose everything each time.

On the pool nothing here changes and nothing is launched by hand. The
platform runs `gwenlake-train`, which FINDS the decorated function:

    $ gwenlake-train --list
    fit
    $ gwenlake-train --steps 30000
    gwenlake: running fit

That is the point of the decorator -- one command for every project, and no
project has to say where it keeps its training.
"""

import random
import time
from pathlib import Path

from gwenlake.training import train


def batches(size: int = 32):
    """Stream, don't load.

    A training set is read batch by batch; the reason a run belongs on the
    pool at all is usually that its data does not fit in memory. Here it is
    noise, so the example runs anywhere.
    """
    while True:
        yield [random.random() for _ in range(size)]


# `steps` and `eval_every` are defaults: `gwenlake-train --steps 500`
# overrides them without touching this file.
#
# `model` names the runs -- two models trained on the same data stay apart in
# the experiment. `tracking=False` runs without touching the server at all.
#
# For data in the Gwenlake catalog, bind it and the function receives it
# alongside `run`:
#
#     from gwenlake.training import train, Input, Output
#
#     @train(training_set=Input("project.dataset"),
#            output=Output("project.model"), steps=2000)
#     def fit(training_set, output, run):
#
@train(steps=600, eval_every=100, model="demo")
def fit(run):
    weight, loss = 0.0, 1.0

    # A previous life may have left state here. `run.resumed` is the only
    # thing to test; `run.resume_path` is the same directory either way.
    if run.resumed:
        weight = float((run.resume_path / "weight.txt").read_text())
        print(f"resumed at step {run.start_step}, weight {weight:.4f}")

    # A plain for loop, with two properties it does not look like it has:
    # it fast-forwards to the last checkpoint on a resume, and it ends when
    # eviction is asked for -- between two steps, never inside one.
    for step, batch in run.steps(batches()):
        time.sleep(0.01)                    # stands in for a real step
        loss = loss * 0.995 + random.uniform(-0.005, 0.005)
        weight += 0.001
        run.log({"loss": loss})

        if run.at_eval:
            # Written AND shipped here rather than after the loop: an evicted
            # run never reaches the end, and the volume it writes to is a disk
            # on one node. What goes to object storage is the copy that
            # outlives the node.
            with run.checkpoint() as ck:
                ck.path("weight.txt").write_text(str(weight))
                ck.metrics = {"accuracy": 1 - loss}
            print(f"step {step}/{run.total_steps} · loss {loss:.4f}")

    # Returned metrics land on the model when the run is bound to one;
    # returning nothing stores run.summary() instead.
    return {"accuracy": 1 - loss, "weight": weight}


if __name__ == "__main__":
    # Only here so the file can be run directly. On the pool nobody calls
    # fit(): `gwenlake-train` finds it. `None` is the client -- a run whose
    # data the platform mounts has no catalog to talk to.
    print(fit(None))
