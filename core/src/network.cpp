#include "daa/network.hpp"

#include <cmath>
#include <queue>
#include <stdexcept>

#include "daa/sorting.hpp"

namespace daa {

std::vector<double> correlation_matrix(const std::vector<Series>& closes) {
    const std::size_t n = closes.size();
    if (n == 0) return {};
    const std::size_t len = closes[0].size();
    if (len < 3) throw std::invalid_argument("need at least 3 closes per series");
    const std::size_t m = len - 1;  // number of returns
    std::vector<Series> z(n, Series(m));
    for (std::size_t i = 0; i < n; ++i) {
        if (closes[i].size() != len) throw std::invalid_argument("all series must have the same length");
        double mean = 0;
        for (std::size_t t = 0; t < m; ++t) {
            if (!(closes[i][t] > 0) || !(closes[i][t + 1] > 0)) throw std::invalid_argument("closes must be positive");
            z[i][t] = std::log(closes[i][t + 1] / closes[i][t]);
            mean += z[i][t];
        }
        mean /= static_cast<double>(m);
        double norm = 0;
        for (double& v : z[i]) {
            v -= mean;
            norm += v * v;
        }
        norm = std::sqrt(norm);
        for (double& v : z[i]) v = norm > 0 ? v / norm : 0.0;  // a flat series correlates 0 with everything
    }
    std::vector<double> rho(n * n, 0.0);
    for (std::size_t i = 0; i < n; ++i) {
        rho[i * n + i] = 1.0;
        for (std::size_t j = i + 1; j < n; ++j) {
            double dot = 0;
            for (std::size_t t = 0; t < m; ++t) dot += z[i][t] * z[j][t];
            dot = std::fmax(-1.0, std::fmin(1.0, dot));
            rho[i * n + j] = rho[j * n + i] = dot;
        }
    }
    return rho;
}

std::vector<double> correlation_distance(const std::vector<double>& rho) {
    std::vector<double> d(rho.size());
    for (std::size_t i = 0; i < rho.size(); ++i) d[i] = std::sqrt(std::fmax(0.0, 2.0 * (1.0 - rho[i])));
    return d;
}

namespace {
void check_square(const std::vector<double>& dist, int n) {
    if (n < 0 || dist.size() != static_cast<std::size_t>(n) * static_cast<std::size_t>(n))
        throw std::invalid_argument("distance matrix must be n x n");
}
}  // namespace

SpanningTree prim_mst(const std::vector<double>& dist, int n) {
    check_square(dist, n);
    SpanningTree t;
    if (n == 0) return t;
    const std::size_t N = static_cast<std::size_t>(n);
    std::vector<double> key(N, INFINITY);  // lightest edge from each outside node to the tree
    std::vector<int> parent(N, -1);
    std::vector<char> in_tree(N, 0);
    key[0] = 0;
    for (std::size_t step = 0; step < N; ++step) {
        std::size_t u = N;
        for (std::size_t v = 0; v < N; ++v) {  // pick the outside node with the lightest connecting edge
            ++t.ops;
            if (!in_tree[v] && (u == N || key[v] < key[u])) u = v;
        }
        if (key[u] == INFINITY) break;  // disconnected graph
        in_tree[u] = 1;
        if (parent[u] >= 0) {
            t.edges.push_back({parent[u], static_cast<int>(u), key[u]});
            t.total += key[u];
        }
        for (std::size_t v = 0; v < N; ++v) {  // relax edges out of u
            ++t.ops;
            double w = dist[u * N + v];
            if (!in_tree[v] && w < key[v]) {
                key[v] = w;
                parent[v] = static_cast<int>(u);
            }
        }
    }
    return t;
}

namespace {
struct UnionFind {
    std::vector<int> parent, rank;
    explicit UnionFind(std::size_t n) : parent(n), rank(n, 0) {
        for (std::size_t i = 0; i < n; ++i) parent[i] = static_cast<int>(i);
    }
    int find(int x) {
        while (parent[static_cast<std::size_t>(x)] != x) {
            parent[static_cast<std::size_t>(x)] = parent[static_cast<std::size_t>(parent[static_cast<std::size_t>(x)])];
            x = parent[static_cast<std::size_t>(x)];
        }
        return x;
    }
    bool unite(int a, int b) {
        a = find(a);
        b = find(b);
        if (a == b) return false;
        if (rank[static_cast<std::size_t>(a)] < rank[static_cast<std::size_t>(b)]) std::swap(a, b);
        parent[static_cast<std::size_t>(b)] = a;
        if (rank[static_cast<std::size_t>(a)] == rank[static_cast<std::size_t>(b)]) ++rank[static_cast<std::size_t>(a)];
        return true;
    }
};
}  // namespace

SpanningTree kruskal_mst(const std::vector<double>& dist, int n) {
    check_square(dist, n);
    SpanningTree t;
    const std::size_t N = static_cast<std::size_t>(n);
    std::vector<WeightedEdge> edges;
    edges.reserve(N * (N - (N > 0 ? 1 : 0)) / 2);
    for (std::size_t i = 0; i < N; ++i)
        for (std::size_t j = i + 1; j < N; ++j) edges.push_back({static_cast<int>(i), static_cast<int>(j), dist[i * N + j]});
    OpCounter ops;
    merge_sort(edges, [](const WeightedEdge& a, const WeightedEdge& b) { return a.w < b.w; }, &ops);
    UnionFind uf(N);
    for (const auto& e : edges) {
        ++ops.count;
        if (uf.unite(e.u, e.v)) {
            t.edges.push_back(e);
            t.total += e.w;
            if (t.edges.size() + 1 == N) break;
        }
    }
    t.ops = ops.count;
    return t;
}

std::vector<std::vector<int>> threshold_graph(const std::vector<double>& rho, int n, double threshold) {
    check_square(rho, n);
    const std::size_t N = static_cast<std::size_t>(n);
    std::vector<std::vector<int>> adj(N);
    for (std::size_t i = 0; i < N; ++i)
        for (std::size_t j = i + 1; j < N; ++j)
            if (rho[i * N + j] >= threshold) {
                adj[i].push_back(static_cast<int>(j));
                adj[j].push_back(static_cast<int>(i));
            }
    return adj;
}

std::vector<int> components_bfs(const std::vector<std::vector<int>>& adj) {
    std::vector<int> label(adj.size(), -1);
    int next = 0;
    for (std::size_t s = 0; s < adj.size(); ++s) {
        if (label[s] >= 0) continue;
        std::queue<int> q;
        q.push(static_cast<int>(s));
        label[s] = next;
        while (!q.empty()) {
            int u = q.front();
            q.pop();
            for (int v : adj[static_cast<std::size_t>(u)])
                if (label[static_cast<std::size_t>(v)] < 0) {
                    label[static_cast<std::size_t>(v)] = next;
                    q.push(v);
                }
        }
        ++next;
    }
    return label;
}

std::vector<int> components_dfs(const std::vector<std::vector<int>>& adj) {
    std::vector<int> label(adj.size(), -1);
    int next = 0;
    for (std::size_t s = 0; s < adj.size(); ++s) {
        if (label[s] >= 0) continue;
        std::vector<int> stack{static_cast<int>(s)};
        label[s] = next;
        while (!stack.empty()) {
            int u = stack.back();
            stack.pop_back();
            for (int v : adj[static_cast<std::size_t>(u)])
                if (label[static_cast<std::size_t>(v)] < 0) {
                    label[static_cast<std::size_t>(v)] = next;
                    stack.push_back(v);
                }
        }
        ++next;
    }
    return label;
}

}  // namespace daa
