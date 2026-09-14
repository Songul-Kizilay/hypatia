# One-shot deferred execution

Hypatia may record one future attempt for one exact background task only after
the trusted local desktop has already recorded a valid deferred-execution
grant. This is a local control-plane trust boundary, not cryptographic user
authentication and not protection against arbitrary malicious code already
running inside the Hypatia process.

The durable schedule binds:

- one schedule ID;
- one scheduler task ID;
- the exact active deferred-grant ID;
- a UTC run time no more than seven days ahead; and
- trusted-local-operator creation provenance.

Creating a schedule runs no research and grants no authority. When the wake-up
fires, Hypatia checks the exact grant ID again and the scheduler independently
revalidates the task, execution, plan digest, plan-derived capabilities, task
bound and remaining execution allowance. It never chooses another task.

## At-most-once boundary

The record is atomically changed from `pending` to `claimed` before the exact
task is attempted. `claimed` is terminal for replay purposes: a crash after the
claim may lose the outcome, but restarting Hypatia will not attempt that record
again. Successful attempts become `triggered`; invalid authority and a busy
desktop worker become `skipped`. All are non-pending and non-recurring.

The desktop holds only one wake-up for the earliest pending record. It uses the
Tk event loop's one-shot `after` callback. There is no background timer thread,
polling loop, recurrence, provider retry, Curiosity scheduling, automatic grant
or automatic budget top-up. Closing the desktop cancels the in-memory callback;
an overdue durable pending record is considered once when the desktop is next
opened.

The store is strict, atomic and bounded to 500 historical records and 4 MiB.
Reaching either bound fails closed instead of dropping or rewriting history.
