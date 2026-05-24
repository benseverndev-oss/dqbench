"""Scoring logic for ER benchmarks."""
from __future__ import annotations

from dqbench.er_ground_truth import ERGroundTruth
from dqbench.models import ERTierResult


def _normalize_pairs(pairs: list[tuple[int, int]]) -> set[tuple[int, int]]:
    """Normalize pairs to (min, max) for symmetric matching."""
    return {(min(a, b), max(a, b)) for a, b in pairs}


def _clusters_from_pairs(pairs: set[tuple[int, int]], n: int) -> tuple[list[int], dict[int, set[int]]]:
    """Union-find over rows 0..n-1; records not in any pair are singletons.

    Returns (root_of_element, members_by_root).
    """
    parent = list(range(n))

    def find(x: int) -> int:
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:  # path compression
            parent[x], x = root, parent[x]
        return root

    for a, b in pairs:
        if a < n and b < n:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)

    roots = [find(i) for i in range(n)]
    members: dict[int, set[int]] = {}
    for i, r in enumerate(roots):
        members.setdefault(r, set()).add(i)
    return roots, members


def _bcubed(pred_pairs: set[tuple[int, int]], true_pairs: set[tuple[int, int]], n: int) -> tuple[float, float, float]:
    """B-Cubed (B³) precision/recall/F1, averaged over all n elements.

    For each element e: precision = |pred_cluster(e) ∩ true_cluster(e)| / |pred_cluster(e)|,
    recall = the same intersection / |true_cluster(e)|.
    """
    if n == 0:
        return 0.0, 0.0, 0.0

    pred_root, pred_members = _clusters_from_pairs(pred_pairs, n)
    true_root, true_members = _clusters_from_pairs(true_pairs, n)

    # Cache intersection size per (pred_root, true_root) pair to avoid recomputation.
    inter_cache: dict[tuple[int, int], int] = {}
    p_sum = 0.0
    r_sum = 0.0
    for e in range(n):
        pc = pred_members[pred_root[e]]
        tc = true_members[true_root[e]]
        key = (pred_root[e], true_root[e])
        inter = inter_cache.get(key)
        if inter is None:
            inter = len(pc & tc)
            inter_cache[key] = inter
        p_sum += inter / len(pc)
        r_sum += inter / len(tc)

    precision = p_sum / n
    recall = r_sum / n
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def score_er_tier(
    predictions: list[tuple[int, int]],
    ground_truth: ERGroundTruth,
    tier: int,
    time_seconds: float,
    memory_mb: float,
) -> ERTierResult:
    """Score ER predictions with pair-level P/R/F1, a confusion matrix, and B³."""
    true_pairs = _normalize_pairs(ground_truth.duplicate_pairs)
    pred_pairs = _normalize_pairs(predictions)

    true_positives = pred_pairs & true_pairs
    false_positives = pred_pairs - true_pairs
    false_negatives = true_pairs - pred_pairs

    tp = len(true_positives)
    fp = len(false_positives)
    fn = len(false_negatives)

    # True negatives: all candidate pairs that are correctly NOT linked.
    n = ground_truth.rows
    total_possible = n * (n - 1) // 2
    tn = max(0, total_possible - tp - fp - fn)

    if tp == 0:
        precision = 0.0
        recall = 0.0
        f1 = 0.0
    else:
        precision = tp / (tp + fp)
        recall = tp / (tp + fn)
        f1 = 2 * precision * recall / (precision + recall)

    bc_p, bc_r, bc_f1 = _bcubed(pred_pairs, true_pairs, n)

    return ERTierResult(
        tier=tier,
        precision=precision,
        recall=recall,
        f1=f1,
        false_positives=fp,
        false_negatives=fn,
        time_seconds=time_seconds,
        memory_mb=memory_mb,
        true_positives=tp,
        true_negatives=tn,
        bcubed_precision=bc_p,
        bcubed_recall=bc_r,
        bcubed_f1=bc_f1,
    )
