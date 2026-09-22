"""HostLimiter (contract §5): bounded, FIFO, hand-off, cancellation-safe. No wall-clock time anywhere."""

from __future__ import annotations

import asyncio
import random

import pytest

from fc2_metadata_core.resource_control import HostKey, HostLimiter, ResourceControlConfigError

from support.resource_fakes import run, until

HOST = HostKey("h.example", 443)




def test_constructor_validation():
    for limit in (0, -1, True, 2.0, "2", None):
        with pytest.raises(ResourceControlConfigError):
            HostLimiter(HOST, limit)  # type: ignore[arg-type]
    with pytest.raises(ResourceControlConfigError):
        HostLimiter("h.example:443", 2)  # type: ignore[arg-type]


def test_never_more_live_permits_than_the_limit_and_the_peak_is_exactly_the_limit():
    async def main():
        limiter = HostLimiter(HOST, 3)
        live = peak = 0
        gate = asyncio.Event()

        async def worker():
            nonlocal live, peak
            with await limiter.acquire():
                live += 1
                peak = max(peak, live)
                await gate.wait()
                live -= 1

        tasks = [asyncio.create_task(worker()) for _ in range(20)]
        await until(lambda: limiter.in_flight == 3 and limiter.waiting == 17)
        assert (live, peak) == (3, 3)
        gate.set()
        await asyncio.gather(*tasks)
        assert (limiter.in_flight, limiter.waiting, peak) == (0, 0, 3)
        assert limiter.snapshot().peak_in_flight == 3

    run(main())


def test_waiters_are_served_strictly_first_come_first_served():
    async def main():
        limiter = HostLimiter(HOST, 1)
        order: list[int] = []
        holder = await limiter.acquire()

        async def waiter(i):
            with await limiter.acquire():
                order.append(i)
                await asyncio.sleep(0)

        tasks = []
        for i in range(10):
            tasks.append(asyncio.create_task(waiter(i)))
            await until(lambda n=i: limiter.waiting == n + 1)
        holder.release()
        await asyncio.gather(*tasks)
        assert order == list(range(10))

    run(main())


def test_a_newcomer_cannot_overtake_a_waiter_or_steal_a_released_permit():
    async def main():
        limiter = HostLimiter(HOST, 1)
        holder = await limiter.acquire()
        got: list[str] = []
        waiter_may_finish = asyncio.Event()

        async def waiter():
            with await limiter.acquire():
                got.append("waiter")
                await waiter_may_finish.wait()

        task = asyncio.create_task(waiter())
        await until(lambda: limiter.waiting == 1)
        holder.release()  # the permit is handed to the waiter *now*, before the waiter task has run
        assert limiter.in_flight == 1 and limiter.waiting == 0
        newcomer = asyncio.create_task(limiter.acquire())
        await until(lambda: got == ["waiter"])
        for _ in range(5):
            await asyncio.sleep(0)
        assert not newcomer.done(), "the newcomer stole the permit the waiter was handed"
        assert limiter.in_flight == 1 and limiter.waiting == 1
        waiter_may_finish.set()
        await task
        permit = await newcomer
        assert limiter.in_flight == 1
        permit.release()
        assert limiter.in_flight == 0

    run(main())


def test_a_newcomer_never_jumps_a_non_empty_queue_even_when_a_slot_is_free_for_an_instant():
    async def main():
        limiter = HostLimiter(HOST, 2)
        first, second = await limiter.acquire(), await limiter.acquire()
        order: list[str] = []

        async def take(name):
            with await limiter.acquire():
                order.append(name)

        queued = asyncio.create_task(take("queued"))
        await until(lambda: limiter.waiting == 1)
        first.release()  # hand-off to `queued`; the slot is never "free" for a newcomer to grab
        late = asyncio.create_task(take("late"))
        await queued
        await late
        assert order == ["queued", "late"]
        second.release()
        assert limiter.in_flight == 0

    run(main())


def test_release_is_idempotent_and_the_context_manager_releases_on_exception():
    async def main():
        limiter = HostLimiter(HOST, 2)
        permit = await limiter.acquire()
        permit.release()
        permit.release()
        permit.release()
        assert limiter.in_flight == 0 and permit.released
        other = await limiter.acquire()  # a double release must not have minted extra capacity
        third = await limiter.acquire()
        blocked = asyncio.create_task(limiter.acquire())
        await until(lambda: limiter.waiting == 1)
        blocked.cancel()
        with pytest.raises(asyncio.CancelledError):
            await blocked
        other.release()
        third.release()
        with pytest.raises(RuntimeError):
            with await limiter.acquire():
                raise RuntimeError("boom")
        assert limiter.in_flight == 0

    run(main())


def test_cancelling_a_waiter_removes_it_and_never_loses_capacity():
    async def main():
        limiter = HostLimiter(HOST, 1)
        holder = await limiter.acquire()
        waiters = [asyncio.create_task(limiter.acquire()) for _ in range(3)]
        await until(lambda: limiter.waiting == 3)
        waiters[1].cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiters[1]
        assert limiter.waiting == 2 and limiter.in_flight == 1
        holder.release()
        first = await waiters[0]
        assert limiter.in_flight == 1
        first.release()
        third = await waiters[2]
        third.release()
        assert (limiter.in_flight, limiter.waiting) == (0, 0)

    run(main())


def test_a_permit_granted_in_the_iteration_the_waiter_is_cancelled_goes_back_to_the_pool():
    async def main():
        limiter = HostLimiter(HOST, 1)
        holder = await limiter.acquire()
        victim = asyncio.create_task(limiter.acquire())
        follower = asyncio.create_task(limiter.acquire())
        await until(lambda: limiter.waiting == 2)
        holder.release()  # hands the permit to `victim` ...
        victim.cancel()  # ... which is cancelled before it ever runs again
        with pytest.raises(asyncio.CancelledError):
            await victim
        permit = await follower  # the permit was NOT leaked: it moved on to the next waiter
        assert limiter.in_flight == 1 and limiter.waiting == 0
        permit.release()
        assert limiter.in_flight == 0
        (await limiter.acquire()).release()

    run(main())


def test_a_granted_then_cancelled_waiter_with_no_follower_returns_the_permit_to_the_pool():
    async def main():
        limiter = HostLimiter(HOST, 1)
        holder = await limiter.acquire()
        victim = asyncio.create_task(limiter.acquire())
        await until(lambda: limiter.waiting == 1)
        holder.release()
        victim.cancel()
        with pytest.raises(asyncio.CancelledError):
            await victim
        assert (limiter.in_flight, limiter.waiting) == (0, 0)

    run(main())


def test_cancelling_a_holder_task_releases_through_the_context_manager():
    async def main():
        limiter = HostLimiter(HOST, 1)
        started = asyncio.Event()

        async def holder():
            with await limiter.acquire():
                started.set()
                await asyncio.Event().wait()

        task = asyncio.create_task(holder())
        await started.wait()
        waiter = asyncio.create_task(limiter.acquire())
        await until(lambda: limiter.waiting == 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        (await waiter).release()
        assert limiter.in_flight == 0

    run(main())


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_100_waiters_with_a_random_subset_cancelled_at_assorted_points_restore_full_capacity(seed):
    rng = random.Random(seed)

    async def main():
        limit = 4
        limiter = HostLimiter(HOST, limit)
        gate = asyncio.Event()
        live = peak = 0

        async def worker(i):
            nonlocal live, peak
            with await limiter.acquire():
                live += 1
                peak = max(peak, live)
                try:
                    await gate.wait()
                    await asyncio.sleep(0)
                finally:
                    live -= 1

        tasks = [asyncio.create_task(worker(i)) for i in range(100)]
        await until(lambda: limiter.in_flight == limit and limiter.waiting == 96)
        # cancel a random subset while everything is parked: waiters and holders alike
        victims = rng.sample(range(100), 45)
        for index in victims:
            tasks[index].cancel()
            if rng.random() < 0.4:
                await asyncio.sleep(0)  # interleave cancellations with scheduling
        gate.set()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        cancelled = {i for i, r in enumerate(results) if isinstance(r, asyncio.CancelledError)}
        assert cancelled <= set(victims)
        assert set(range(100)) - cancelled  # some completed normally
        assert peak <= limit
        # capacity fully restored: nothing held, nobody queued ...
        assert (limiter.in_flight, limiter.waiting) == (0, 0)
        # ... and it admits exactly `limit` new holders (no phantom holder, no lost slot)
        permits = [await limiter.acquire() for _ in range(limit)]
        extra = asyncio.create_task(limiter.acquire())
        await until(lambda: limiter.waiting == 1)
        assert limiter.in_flight == limit
        extra.cancel()
        with pytest.raises(asyncio.CancelledError):
            await extra
        for permit in permits:
            permit.release()
        assert (limiter.in_flight, limiter.waiting) == (0, 0)

    run(main())


def test_cancelling_every_waiter_leaves_only_the_holders():
    async def main():
        limiter = HostLimiter(HOST, 2)
        holders = [await limiter.acquire(), await limiter.acquire()]
        waiters = [asyncio.create_task(limiter.acquire()) for _ in range(50)]
        await until(lambda: limiter.waiting == 50)
        for task in waiters:
            task.cancel()
        await asyncio.gather(*waiters, return_exceptions=True)
        assert (limiter.in_flight, limiter.waiting) == (2, 0)
        for holder in holders:
            holder.release()
        assert limiter.in_flight == 0

    run(main())
