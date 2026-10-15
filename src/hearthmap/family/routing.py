# ruff: noqa: E501
"""Offline road-network routing (decision recorded in docs/research/m2a-routing-decision.md).

A directed graph is built from OSM ways (shared vertices identified by exact rounded coordinates, one-way
tags honoured). Travel time is BASELINE_DRIVE_TIME: length / assumed free-flow speed per highway class.
Multi-source Dijkstra gives, for every node, the nearest facility, time and network distance. A node that is
not reachable stays UNRESOLVED (inf); it is never filled with a straight-line estimate.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

import numpy as np

INF = float("inf")


@dataclass
class Network:
    xy: np.ndarray  # (n,2) metres, canonical CRS
    indptr: np.ndarray  # CSR over directed edges
    indices: np.ndarray
    length_m: np.ndarray
    hw_code: np.ndarray  # index into ``classes``
    classes: list[str]
    component: np.ndarray  # connected-component id per node (undirected)
    component_size: np.ndarray  # nodes per component id

    def edge_time_s(self, speeds_kmh: dict[str, float], multiplier: float = 1.0) -> np.ndarray:
        v = (
            np.array([speeds_kmh.get(c, 0.0) * multiplier for c in self.classes], dtype=float) / 3.6
        )  # m/s
        if (v <= 0).any():
            raise ValueError(
                f"no speed assumption for classes {[c for c, s in zip(self.classes, v, strict=True) if s <= 0]}"
            )
        return self.length_m / v[self.hw_code]


def _components(n: int, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    parent = np.arange(n)

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in zip(u.tolist(), v.tolist(), strict=True):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    roots = np.fromiter((find(i) for i in range(n)), dtype=np.int64, count=n)
    _, comp = np.unique(roots, return_inverse=True)
    return comp


def build_network(ways: list[dict]) -> Network:
    """``ways``: dicts with ``keys`` (int64 vertex keys), ``xy`` (k,2) metres, ``highway`` and optional ``oneway``."""
    classes = sorted({w["highway"] for w in ways})
    cmap = {c: i for i, c in enumerate(classes)}
    all_keys = np.concatenate([w["keys"] for w in ways])
    all_xy = np.concatenate([w["xy"] for w in ways])
    uniq, first, inv = np.unique(all_keys, return_index=True, return_inverse=True)
    xy = all_xy[first]
    us, vs, ls, hs = [], [], [], []
    off = 0
    for w in ways:
        k = len(w["keys"])
        idx = inv[off : off + k]
        off += k
        if k < 2:
            continue
        a, b = idx[:-1], idx[1:]
        keep = a != b
        a, b = a[keep], b[keep]
        d = np.hypot(*(all_xy[off - k + 1 : off][keep] - all_xy[off - k : off - 1][keep]).T)
        ow = str(w.get("oneway") or "no").lower()
        if ow in ("yes", "true", "1"):
            us.append(a), vs.append(b), ls.append(d)
        elif ow == "-1":
            us.append(b), vs.append(a), ls.append(d)
        else:
            (
                us.append(np.concatenate([a, b])),
                vs.append(np.concatenate([b, a])),
                ls.append(np.concatenate([d, d])),
            )
        hs.append(np.full(len(us[-1]), cmap[w["highway"]], dtype=np.int16))
    u, v, ln, hw = (np.concatenate(x) for x in (us, vs, ls, hs))
    order = np.argsort(u, kind="stable")
    u, v, ln, hw = u[order], v[order], ln[order], hw[order]
    n = len(uniq)
    indptr = np.zeros(n + 1, dtype=np.int64)
    np.add.at(indptr, u + 1, 1)
    indptr = np.cumsum(indptr)
    comp = _components(n, u, v)
    return Network(xy, indptr, v.astype(np.int64), ln, hw, classes, comp, np.bincount(comp))


def reverse(net: Network) -> Network:
    """The same network with every directed edge flipped (travel TO a facility)."""
    u = np.repeat(np.arange(len(net.indptr) - 1), np.diff(net.indptr))
    order = np.argsort(net.indices, kind="stable")
    n = len(net.indptr) - 1
    indptr = np.zeros(n + 1, dtype=np.int64)
    np.add.at(indptr, net.indices + 1, 1)
    return Network(
        net.xy,
        np.cumsum(indptr),
        u[order],
        net.length_m[order],
        net.hw_code[order],
        net.classes,
        net.component,
        net.component_size,
    )


def multi_source_dijkstra(
    net: Network, edge_time_s: np.ndarray, sources: np.ndarray, source_labels: np.ndarray, max_time_s: float = INF
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:  # fmt: skip
    """Return (time_s, distance_m, label) per node; unreachable nodes get inf / inf / -1."""
    n = len(net.indptr) - 1
    t = np.full(n, INF)
    dist = np.full(n, INF)
    lab = np.full(n, -1, dtype=np.int64)
    heap: list[tuple[float, int]] = []
    for s, lb in zip(sources.tolist(), source_labels.tolist(), strict=True):
        if t[s] > 0 or (t[s] == 0 and lb < lab[s]):
            t[s], dist[s], lab[s] = 0.0, 0.0, lb
        heapq.heappush(heap, (0.0, s))
    indptr, indices, ln = net.indptr, net.indices, net.length_m
    tl, dl, ll = t.tolist(), dist.tolist(), lab.tolist()
    et = edge_time_s.tolist()
    lnl = ln.tolist()
    ip = indptr.tolist()
    ix = indices.tolist()
    pop, push = heapq.heappop, heapq.heappush
    while heap:
        d, u = pop(heap)
        if d > tl[u] or d > max_time_s:
            continue
        for e in range(ip[u], ip[u + 1]):
            v = ix[e]
            nd = d + et[e]
            # deterministic tie-break: smaller label wins on equal time
            if nd < tl[v] or (nd == tl[v] and ll[u] < ll[v]):
                improved = nd < tl[v]
                tl[v], dl[v], ll[v] = nd, dl[u] + lnl[e], ll[u]
                if improved:
                    push(heap, (nd, v))
    return np.array(tl), np.array(dl), np.array(ll, dtype=np.int64)


class ListGraph:
    """CSR arrays as Python lists, for many cheap bounded searches."""

    def __init__(self, net: Network, edge_time_s: np.ndarray) -> None:
        self.ip, self.ix, self.et = net.indptr.tolist(), net.indices.tolist(), edge_time_s.tolist()


def bounded_reach(g: ListGraph, source: int, max_time_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Nodes reachable from ``source`` within ``max_time_s`` and their times (one facility)."""
    best = {source: 0.0}
    heap = [(0.0, source)]
    pop, push = heapq.heappop, heapq.heappush
    ip, ix, et = g.ip, g.ix, g.et
    while heap:
        d, u = pop(heap)
        if d > best[u]:
            continue
        for e in range(ip[u], ip[u + 1]):
            nd = d + et[e]
            if nd > max_time_s:
                continue
            v = ix[e]
            if nd < best.get(v, INF):
                best[v] = nd
                push(heap, (nd, v))
    return np.fromiter(best.keys(), dtype=np.int64, count=len(best)), np.fromiter(
        best.values(), dtype=float, count=len(best)
    )
