#include "daa/bench.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <functional>
#include <map>
#include <numeric>
#include <random>
#include <stdexcept>

#include "daa/backtest.hpp"
#include "daa/network.hpp"
#include "daa/portfolio.hpp"
#include "daa/search.hpp"
#include "daa/sorting.hpp"
#include "daa/topo.hpp"
#include "daa/trend.hpp"

namespace daa {

namespace {

using Rng = std::mt19937_64;

std::vector<double> make_values(std::size_t n, const std::string& input, Rng& rng) {
    std::vector<double> v(n);
    std::uniform_real_distribution<double> u(0.0, 1.0);
    if (input == "random") {
        for (auto& x : v) x = u(rng);
        return v;
    }
    for (std::size_t i = 0; i < n; ++i) v[i] = static_cast<double>(i);
    if (input == "nearly_sorted" && n > 1) {
        std::uniform_int_distribution<std::size_t> pos(0, n - 2);
        for (std::size_t k = 0; k < std::max<std::size_t>(1, n / 100); ++k) {
            std::size_t i = pos(rng);
            std::swap(v[i], v[i + 1]);
        }
    } else if (input != "sorted") {
        throw std::invalid_argument("input must be random, sorted or nearly_sorted");
    }
    return v;
}

std::vector<double> random_distance_matrix(std::size_t n, Rng& rng) {
    std::uniform_real_distribution<double> u(0.0, 2.0);
    std::vector<double> d(n * n, 0.0);
    for (std::size_t i = 0; i < n; ++i)
        for (std::size_t j = i + 1; j < n; ++j) d[i * n + j] = d[j * n + i] = u(rng);
    return d;
}

std::vector<std::pair<int, int>> random_edges(std::size_t n, std::size_t m, bool dag, Rng& rng) {
    std::vector<std::pair<int, int>> e;
    if (n < 2) return e;
    std::uniform_int_distribution<int> node(0, static_cast<int>(n) - 1);
    e.reserve(m);
    while (e.size() < m) {
        int a = node(rng), b = node(rng);
        if (a == b) continue;
        if (dag && a > b) std::swap(a, b);
        e.push_back({a, b});
    }
    return e;
}

std::vector<std::vector<int>> adjacency(std::size_t n, const std::vector<std::pair<int, int>>& edges) {
    std::vector<std::vector<int>> adj(n);
    for (auto [a, b] : edges) {
        adj[static_cast<std::size_t>(a)].push_back(b);
        adj[static_cast<std::size_t>(b)].push_back(a);
    }
    return adj;
}

// A prepared run: setup builds the input (not timed); the returned function runs the algorithm once.
using Prepared = std::function<std::uint64_t()>;
using Factory = std::function<Prepared(std::size_t n, const std::string& input, Rng& rng)>;

const std::map<std::string, Factory>& registry() {
    static const std::map<std::string, Factory> r = {
        {"merge_sort", [](std::size_t n, const std::string& in, Rng& rng) -> Prepared {
             auto base = make_values(n, in, rng);
             return [base] { auto v = base; OpCounter ops; merge_sort(v, &ops); return ops.count; };
         }},
        {"quicksort_random", [](std::size_t n, const std::string& in, Rng& rng) -> Prepared {
             auto base = make_values(n, in, rng);
             return [base] { auto v = base; OpCounter ops; quicksort(v, Pivot::Random, 7, &ops); return ops.count; };
         }},
        {"quicksort_last", [](std::size_t n, const std::string& in, Rng& rng) -> Prepared {
             auto base = make_values(n, in, rng);
             return [base] { auto v = base; OpCounter ops; quicksort(v, Pivot::Last, 7, &ops); return ops.count; };
         }},
        {"count_inversions", [](std::size_t n, const std::string& in, Rng& rng) -> Prepared {
             auto base = make_values(n, in, rng);
             return [base] { OpCounter ops; count_inversions(base, &ops); return ops.count; };
         }},
        {"count_inversions_naive", [](std::size_t n, const std::string& in, Rng& rng) -> Prepared {
             auto base = make_values(n, in, rng);
             return [base] { OpCounter ops; count_inversions_naive(base, &ops); return ops.count; };
         }},
        {"binary_search", [](std::size_t n, const std::string&, Rng& rng) -> Prepared {
             auto base = make_values(n, "sorted", rng);
             std::vector<double> queries(100000);
             std::uniform_real_distribution<double> u(0.0, static_cast<double>(n));
             for (auto& q : queries) q = u(rng);
             return [base, queries] {
                 [[maybe_unused]] static volatile std::uint64_t guard = 0;  // keeps the searches from being optimised away
                 std::uint64_t sink = 0;
                 for (double q : queries) sink += lower_bound_idx(base, q);
                 guard = sink;
                 // 100,000 searches, each about log2(n) + 1 comparisons.
                 return static_cast<std::uint64_t>(queries.size() * (std::log2(static_cast<double>(base.size()) + 1) + 1));
             };
         }},
        {"lis_patience", [](std::size_t n, const std::string& in, Rng& rng) -> Prepared {
             auto base = make_values(n, in, rng);
             return [base] { OpCounter ops; lis_length(base, &ops); return ops.count; };
         }},
        {"lis_dp", [](std::size_t n, const std::string& in, Rng& rng) -> Prepared {
             auto base = make_values(n, in, rng);
             return [base] { OpCounter ops; lis_length_dp(base, &ops); return ops.count; };
         }},
        {"mann_kendall", [](std::size_t n, const std::string& in, Rng& rng) -> Prepared {
             auto base = make_values(n, in, rng);
             return [base] { mann_kendall(base); return std::uint64_t{0}; };
         }},
        {"prim_mst", [](std::size_t n, const std::string&, Rng& rng) -> Prepared {
             auto d = random_distance_matrix(n, rng);
             return [d, n] { return prim_mst(d, static_cast<int>(n)).ops; };
         }},
        {"kruskal_mst", [](std::size_t n, const std::string&, Rng& rng) -> Prepared {
             auto d = random_distance_matrix(n, rng);
             return [d, n] { return kruskal_mst(d, static_cast<int>(n)).ops; };
         }},
        {"topological_sort", [](std::size_t n, const std::string&, Rng& rng) -> Prepared {
             auto e = random_edges(n, 4 * n, true, rng);
             return [e, n] { topological_sort(static_cast<int>(n), e); return static_cast<std::uint64_t>(n + e.size()); };
         }},
        {"bfs_components", [](std::size_t n, const std::string&, Rng& rng) -> Prepared {
             auto adj = adjacency(n, random_edges(n, n, false, rng));
             return [adj, n] { components_bfs(adj); return static_cast<std::uint64_t>(3 * n); };
         }},
        {"dfs_components", [](std::size_t n, const std::string&, Rng& rng) -> Prepared {
             auto adj = adjacency(n, random_edges(n, n, false, rng));
             return [adj, n] { components_dfs(adj); return static_cast<std::uint64_t>(3 * n); };
         }},
        {"tree_independent_set", [](std::size_t n, const std::string&, Rng& rng) -> Prepared {
             std::vector<std::pair<int, int>> e;
             std::vector<double> w(n);
             std::uniform_real_distribution<double> u(0.0, 100.0);
             for (std::size_t i = 0; i < n; ++i) {
                 w[i] = u(rng);
                 if (i) e.push_back({std::uniform_int_distribution<int>(0, static_cast<int>(i) - 1)(rng), static_cast<int>(i)});
             }
             return [e, w, n] { tree_max_independent_set(static_cast<int>(n), e, w); return static_cast<std::uint64_t>(n); };
         }},
        {"knapsack_01", [](std::size_t n, const std::string&, Rng& rng) -> Prepared {
             // n = capacity W with 30 items: time grows with W (pseudo-polynomial).
             std::vector<double> v(30);
             std::vector<long long> w(30);
             std::uniform_real_distribution<double> u(1.0, 100.0);
             std::uniform_int_distribution<long long> wt(1, std::max<long long>(1, static_cast<long long>(n) / 5));
             for (std::size_t i = 0; i < 30; ++i) { v[i] = u(rng); w[i] = wt(rng); }
             return [v, w, n] { return knapsack_01(v, w, static_cast<long long>(n)).cells; };
         }},
        {"fractional_knapsack", [](std::size_t n, const std::string&, Rng& rng) -> Prepared {
             std::vector<double> v(n), w(n);
             std::uniform_real_distribution<double> u(1.0, 100.0);
             for (std::size_t i = 0; i < n; ++i) { v[i] = u(rng); w[i] = u(rng); }
             return [v, w, n] { fractional_knapsack(v, w, 25.0 * static_cast<double>(n)); return std::uint64_t{0}; };
         }},
        {"subset_sum_backtracking", [](std::size_t n, const std::string&, Rng& rng) -> Prepared {
             SubsetProblem p;
             std::uniform_real_distribution<double> u(50.0, 150.0);
             for (std::size_t i = 0; i < n; ++i) { p.cost.push_back(1000 * std::round(u(rng))); p.score.push_back(u(rng)); p.group.push_back(static_cast<int>(i % 6)); }
             p.capacity = 1000.0 * 100 * std::max<double>(1.0, static_cast<double>(n) / 2.5);
             p.max_items = 10;
             p.max_per_group = 3;
             return [p] { return subset_sum_backtracking(p).nodes; };
         }},
        {"subset_sum_brute_force", [](std::size_t n, const std::string&, Rng& rng) -> Prepared {
             SubsetProblem p;
             std::uniform_real_distribution<double> u(50.0, 150.0);
             for (std::size_t i = 0; i < n; ++i) { p.cost.push_back(1000 * std::round(u(rng))); p.score.push_back(u(rng)); p.group.push_back(static_cast<int>(i % 6)); }
             p.capacity = 1000.0 * 100 * std::max<double>(1.0, static_cast<double>(n) / 2.5);
             p.max_items = 10;
             p.max_per_group = 3;
             return [p] { return subset_sum_brute_force(p).nodes; };
         }},
        {"coin_change", [](std::size_t n, const std::string&, Rng& rng) -> Prepared {
             std::vector<long long> prices(5);
             std::uniform_int_distribution<long long> pr(97, 2999);
             for (auto& p : prices) p = pr(rng);
             return [prices, n] { coin_change_max_spend(prices, static_cast<long long>(n)); return static_cast<std::uint64_t>(5 * n); };
         }},
        {"interval_scheduling", [](std::size_t n, const std::string&, Rng& rng) -> Prepared {
             std::vector<int> s(n), e(n);
             std::uniform_int_distribution<int> st(0, static_cast<int>(10 * n)), len(1, 60);
             for (std::size_t i = 0; i < n; ++i) { s[i] = st(rng); e[i] = s[i] + len(rng); }
             return [s, e] { interval_scheduling(s, e); return std::uint64_t{0}; };
         }},
        {"hindsight_dag", [](std::size_t n, const std::string&, Rng& rng) -> Prepared {
             std::vector<Series> closes(n, Series(50));
             std::normal_distribution<double> g(0.0, 0.02);
             for (std::size_t s = 0; s < 50; ++s) {
                 double p = 100;
                 for (std::size_t d = 0; d < n; ++d) { p *= std::exp(g(rng)); closes[d][s] = p; }
             }
             return [closes, n] { hindsight_longest_path(closes, 60, 0.001); return static_cast<std::uint64_t>(n * 60 * 50); };
         }},
    };
    return r;
}

}  // namespace

std::vector<std::string> benchmark_names() {
    std::vector<std::string> out;
    for (const auto& kv : registry()) out.push_back(kv.first);
    return out;
}

BenchResult run_benchmark(const std::string& name, long long n, const std::string& input, std::uint64_t seed,
                          int repeats) {
    auto it = registry().find(name);
    if (it == registry().end()) throw std::invalid_argument("unknown algorithm " + name);
    if (n < 1) throw std::invalid_argument("n must be positive");
    Rng rng(seed);
    Prepared run = it->second(static_cast<std::size_t>(n), input, rng);
    BenchResult best{INFINITY, 0};
    for (int r = 0; r < std::max(1, repeats); ++r) {
        auto t0 = std::chrono::steady_clock::now();
        std::uint64_t ops = run();
        double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
        if (ms < best.millis) best = {ms, ops};
    }
    return best;
}

}  // namespace daa
