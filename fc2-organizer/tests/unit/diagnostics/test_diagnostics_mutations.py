"""P4-C9 contract section 28.5 (non-vacuity): source-level mutation testing of the validation layer.

Each mutant is the *real* ``validation.py`` source with one deliberate defect, compiled into a throw-away module
object and swapped into ``build`` for the duration of one ``with`` block. Nothing in the repository is modified: the
production source files are hashed before and after (SHA-256) and the identity of every function the mutant could
have replaced is compared again once the block ends (the "hash / object restore proof"). A mutant is *killed* when,
for the scenario its defect is meant to expose, the unmutated code fails closed (typed error, no hooks) while the
mutant accepts the input, raises a different error, or runs a hook."""

from __future__ import annotations

import ast
import contextlib
import dataclasses
import hashlib
import importlib
import pathlib
import types

import pytest
from fc2_organizer import diagnostics
from fc2_organizer.diagnostics import (
    DiagnosticsIntegrityError,
    DiagnosticsResourceLimitError,
    DiagnosticsUnsafeValueError,
    TimingPolicy,
    validation,
)
from fc2_organizer.orchestration import BatchPreview, ItemExecution
from fc2_organizer.orchestration import RetryKind as K

from fc2_organizer.planning import OrganizePlan
from . import _builders as b

build_module = importlib.import_module("fc2_organizer.diagnostics.build")
PRODUCTION = pathlib.Path(diagnostics.__file__).parent
FILES = sorted(PRODUCTION.glob("*.py"))
AGG = ("metadata_batch", "items", 0, "aggregation_result")


def source_hashes():
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in FILES}


def public_identities():
    return {(module.__name__, name): id(value) for module in (validation, build_module)
            for name, value in vars(module).items() if callable(value) and not name.startswith("__")}


def compile_mutant(filename, old, new):
    """The real source with one defect, executed in a copy of the *real module's own namespace* with its import
    statements dropped: the mutant therefore uses exactly the class objects the real module (and the test graphs)
    use, however ``sys.modules`` was reshuffled by other test modules."""
    path = PRODUCTION / filename
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, "the mutation target must occur exactly once: %r" % old
    tree = ast.parse(text.replace(old, new), filename=str(path))
    tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
    real = {"validation.py": validation}[filename]
    module = types.ModuleType("mutant_" + path.stem)
    module.__dict__.update({k: v for k, v in vars(real).items() if not k.startswith("__")})
    module.__file__ = str(path)
    exec(compile(tree, str(path), "exec"), module.__dict__)  # noqa: S102 -- test-only mutant
    return module


@contextlib.contextmanager
def mutation(old, new, filename="validation.py"):
    """Swap the mutated snapshot builders into ``build``; prove afterwards that everything was restored."""
    hashes, identities = source_hashes(), public_identities()
    mutant = compile_mutant(filename, old, new)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(build_module, "build_preview_snapshot", mutant.build_preview_snapshot)
        patch.setattr(build_module, "build_execution_snapshot", mutant.build_execution_snapshot)
        yield mutant
    assert source_hashes() == hashes, "a production source file changed"
    assert public_identities() == identities, "a patched object was not restored"


def outcome(kind, graph):
    """``(exception class or None, hook hits)`` of one build."""
    b.reset_hits()
    try:
        b.BUILD[kind](graph)
    except Exception as exc:  # noqa: BLE001
        return type(exc), sum(b.HITS.values())
    return None, sum(b.HITS.values())


def killed(kind, scenario, old, new, *, expected=DiagnosticsIntegrityError, filename="validation.py"):
    """The unmutated code gives ``expected`` with no hook; the mutant does not."""
    graph = scenario()
    assert outcome(kind, graph) == (expected, 0), "the scenario must fail closed on the real code"
    graph = scenario()
    with mutation(old, new, filename):
        got, hits = outcome(kind, graph)
    return got is not expected or hits > 0


# ---- scenarios


def _fresh(factory, mutate):
    graph = factory()
    mutate(graph)
    return graph


def scenario(kind, mutate):
    factory = b.FACTORY[kind]
    return lambda: _fresh(factory, mutate)


# ---- fail-closed / local validation mutants


def hostile_plan(graph):
    b.plant_object(graph, ("items", 0, "plan"))


def retarget_library_root(graph):
    root = graph.library_root
    b.poke(graph, library_root=root + "-x")
    for item in graph.items:
        b.poke(item.plan, library_root=root + "-x")


def equal_plan_clone(graph):
    item = graph.items[1]
    b.poke(item.retry_material, plan=dataclasses.replace(item.plan))


def swap_resume_checkpoint(graph):
    b.poke(graph.items[1].retry_material, checkpoint=b.execution_graph().items[1].execution.checkpoint)


def fresh_with_checkpoint(graph):
    b.poke(graph.items[2].retry_material, checkpoint=b.execution_graph().items[1].execution.checkpoint)


def tiny_retention_budget(graph):
    b.poke(graph, retention_budget_bytes=1)


MUTANTS = [
    ("skip SourceResult.metadata exact-type check", "preview",
     lambda g: b.poke(g.metadata_batch.items[0].aggregation_result.source_results[0], metadata=b.Hostile()),
     'if type(result.metadata) is not NormalizedMetadata:', 'if False:'),
    ("skip OrganizePlan exact-type check", "preview", hostile_plan,
     'if type(plan) is not OrganizePlan:', 'if False:'),
    ("skip ArtifactWriteRequest exact-type check", "preview",
     lambda g: b.plant_element(g, ("items", 0, "preflight", "artifacts"), b.Hostile()),
     'if type(request) is not ArtifactWriteRequest:', 'if False:'),
    ("skip BatchResult exact-type check", "preview", lambda g: b.poke(g, metadata_batch=b.Hostile()),
     'if type(batch) is not BatchResult:', 'if False:'),
    ("skip the plan layout check (9.6.5 target directory)", "preview", retarget_library_root,
     'if td != os.path.join(plan.library_root, plan.canonical_number):', 'if False:'),
    ("skip retry_material presence relation", "execution",
     lambda g: b.poke(g.items[1], retry_material=None),
     'if (material is not None) != (expected in _MATERIAL_KINDS):', 'if False:'),
    ("skip material.plan identity", "execution", equal_plan_clone,
     'if material.plan is not item.plan:', 'if False:'),
    ("skip RESUME checkpoint identity", "execution", swap_resume_checkpoint,
     'or material.checkpoint is not execution.checkpoint):', 'or False):'),
    ("skip FRESH_REEXECUTE no-checkpoint rule", "execution", fresh_with_checkpoint,
     'elif expected is RetryKind.FRESH_REEXECUTE and material.checkpoint is not None:', 'elif False:'),
    ("skip the retained retry payload budget", "execution", tiny_retention_budget,
     'if retained_retry_bytes(items) > limit:', 'if False:'),
    ("skip the retained artifact budget", "preview", tiny_retention_budget,
     'if retained_preview_bytes(items) > limit:', 'if False:'),
]


@pytest.mark.parametrize(("label", "kind", "mutate", "old", "new"), MUTANTS, ids=[m[0] for m in MUTANTS])
def test_each_validation_mutant_is_killed(label, kind, mutate, old, new):
    assert killed(kind, scenario(kind, mutate), old, new), label


def test_mutant_skipping_the_item_limit_is_killed():
    def over(graph):
        b.poke(graph, items=tuple(object() for _ in range(2001)))

    assert killed("preview", scenario("preview", over),
                  'require_bounded_tuple(items, MAX_DIAGNOSTIC_ITEMS, "BatchPreview.items must be an exact tuple",',
                  'require_bounded_tuple(items, 10**9, "BatchPreview.items must be an exact tuple",',
                  expected=DiagnosticsResourceLimitError)


def test_mutant_trusting_the_retry_kind_property_is_killed(monkeypatch):
    graph = b.execution_graph()  # built first: the constructors validate with the real property
    original = ItemExecution.__dict__["retry_kind"]
    monkeypatch.setattr(ItemExecution, "retry_kind", property(lambda self: K.DEFERRED if self.index == 0 else
                                                              original.fget(self)))
    assert outcome("execution", graph)[0] is DiagnosticsIntegrityError  # the real check notices
    with mutation('if kind is not checked[position][1]:', 'if False:'):
        got, _ = outcome("execution", graph)
    assert got is not DiagnosticsIntegrityError  # the mutant trusts the lying property


def test_mutant_reading_summary_before_the_validation_steps_is_killed(monkeypatch):
    reads = []
    original = BatchPreview.__dict__["summary"]
    monkeypatch.setattr(BatchPreview, "summary", property(lambda self: reads.append(1) or original.fget(self)))
    graph = b.preview_graph()
    b.poke(graph.items[1], state=b.Hostile())  # a broken dependency graph: the property must not be read
    assert outcome("preview", graph)[0] is DiagnosticsIntegrityError and reads == []
    with mutation('    items = preview.items\n    require_bounded_tuple(items, MAX_DIAGNOSTIC_ITEMS, "BatchPreview.items must be an exact tuple",',
                  '    items = preview.items\n    preview.summary\n    require_bounded_tuple(items, MAX_DIAGNOSTIC_ITEMS, "BatchPreview.items must be an exact tuple",'):
        outcome("preview", graph)
    assert reads != []


def test_mutant_running_phase_r_before_phase_v_is_killed():
    """The membership test of the (hostile) id container runs before its Phase V completed."""
    def plant(graph):
        aggregation = graph.metadata_batch.items[0].aggregation_result
        b.poke(aggregation, contributing_source_ids=("src_a", b.EvilStr("src_c")))

    assert killed("preview", scenario("preview", plant), "    require_bounded_tuple(contributing,",
                  "    _probe = results[1].source_id in contributing\n    require_bounded_tuple(contributing,")


def test_mutant_calling_an_upstream_validator_is_caught_by_the_tripwire(monkeypatch):
    """Mutation "production code calls an upstream ``__post_init__``": the no-validator trip-wire fires."""

    calls = []
    graph = b.preview_graph()  # built first: the constructors run the real validators
    monkeypatch.setattr(OrganizePlan, "__post_init__", lambda self: calls.append(1))
    b.BUILD["preview"](graph)
    assert calls == []
    with mutation('    for text in (plan.source_path, plan.library_root):',
                  '    plan.__post_init__()\n    for text in (plan.source_path, plan.library_root):'):
        b.BUILD["preview"](graph)
    assert calls  # the real code never calls it; the mutant does, and the tripwire counts it


def test_mutant_with_a_side_effect_is_caught_by_the_trap(monkeypatch):
    """Mutation "projection calls ``open``": the side-effect trap of test_diagnostics_no_side_effects fires."""
    import builtins

    monkeypatch.setattr(builtins, "open", lambda *a, **k: (_ for _ in ()).throw(AssertionError("open")))
    graph = b.preview_graph()
    b.BUILD["preview"](graph)  # real code: no open
    with mutation("def build_preview_snapshot(preview: object, path_policy: object, timing_policy: object) -> BatchSnapshot:\n"
                  '    """Contract section 24.2 steps 3-7 for a ``BatchPreview``."""',
                  "def build_preview_snapshot(preview: object, path_policy: object, timing_policy: object) -> BatchSnapshot:\n"
                  '    """Contract section 24.2 steps 3-7 for a ``BatchPreview``."""\n    open("x")'):
        with pytest.raises(AssertionError):
            b.BUILD["preview"](graph)


# ---- numeric totality mutants (R3-01), source level


def backoff_graph(value):
    def mutate(graph):
        attempt = graph.metadata_batch.items[0].aggregation_result.source_execution_traces[1].attempts[1]
        b.poke(attempt, backoff_before_seconds=value)

    return scenario("preview", mutate)


def include_outcome(scenario_factory, old, new):
    graph = scenario_factory()
    real = None
    try:
        build_module.build_preview_diagnostics(graph, timing_policy=TimingPolicy.INCLUDE)
    except Exception as exc:  # noqa: BLE001
        real = type(exc)
    graph = scenario_factory()
    with mutation(old, new):
        try:
            build_module.build_preview_diagnostics(graph, timing_policy=TimingPolicy.INCLUDE)
            mutant = None
        except Exception as exc:  # noqa: BLE001
            mutant = type(exc)
    return real, mutant


NUMERIC = [
    ("INCLUDE does not gate a huge backoff int", 10**400, 'if value > MAX_TIMING_SECONDS:', 'if False:'),
    ("INCLUDE does not gate a huge backoff float (convert first)", 1e306, 'if value > BACKOFF_SECONDS_GATE:',
     'if False:'),
    ("backoff upper bound shifted by one second", 604801, 'if value > MAX_TIMING_SECONDS:',
     'if value > MAX_TIMING_SECONDS + 1:'),
    ("backoff float bound removed (R3 truncation)", 604800.0005, 'if value > BACKOFF_SECONDS_GATE:',
     'if int(value * 1000) > MAX_TIMING_MS:'),
]


@pytest.mark.parametrize(("label", "value", "old", "new"), NUMERIC, ids=[n[0] for n in NUMERIC])
def test_each_numeric_mutant_is_killed(label, value, old, new):
    real, mutant = include_outcome(backoff_graph(value), old, new)
    assert real is DiagnosticsUnsafeValueError, label
    assert mutant is not DiagnosticsUnsafeValueError, label  # accepted, or a bare / different error escaped


# ---- the restore proof itself


def test_the_restore_proof_is_not_vacuous():
    """Leaving a patch in place would be detected: the identity map differs while a mutant is installed."""
    hashes, identities = source_hashes(), public_identities()
    mutant = compile_mutant("validation.py", "if type(plan) is not OrganizePlan:", "if False:")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(build_module, "build_preview_snapshot", mutant.build_preview_snapshot)
        assert public_identities() != identities
    assert public_identities() == identities and source_hashes() == hashes


def test_a_mutation_target_that_does_not_exist_is_an_error():
    with pytest.raises(AssertionError):
        compile_mutant("validation.py", "this text does not occur in the module", "x")


def test_the_production_sources_are_unchanged_by_this_module():
    hashes = source_hashes()
    assert len(hashes) == 7 and all(len(value) == 64 for value in hashes.values())
