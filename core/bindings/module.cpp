// Python bindings for the C++ algorithm library (module name: daa_core).
// The algorithms live in core/src; this file only converts between Python and C++ types.
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <numeric>
#include <string>

#include "daa/backtest.hpp"
#include "daa/bench.hpp"
#include "daa/classify.hpp"
#include "daa/features.hpp"
#include "daa/indicators.hpp"
#include "daa/network.hpp"
#include "daa/portfolio.hpp"

#include <chrono>
#include "daa/search.hpp"
#include "daa/sorting.hpp"
#include "daa/topo.hpp"
#include "daa/trend.hpp"
#include "daa/version.hpp"

namespace py = pybind11;
using daa::Series;

namespace {

using InArray = py::array_t<double, py::array::c_style | py::array::forcecast>;

Series to_series(const InArray& a) {
    if (a.ndim() != 1) throw std::invalid_argument("expected a 1-D array");
    auto r = a.unchecked<1>();
    Series s(static_cast<std::size_t>(r.shape(0)));
    for (py::ssize_t i = 0; i < r.shape(0); ++i) s[static_cast<std::size_t>(i)] = r(i);
    return s;
}

py::array_t<double> to_array(const Series& s) {
    py::array_t<double> a(static_cast<py::ssize_t>(s.size()));
    std::copy(s.begin(), s.end(), a.mutable_data());
    return a;
}

py::dict feature_dict(const daa::FeatureMap& f) {
    py::dict d;
    for (const auto& [k, v] : f) d[py::str(k)] = to_array(v);
    return d;
}

// Stable order of indices that sorts keys ascending (or descending), using merge sort.
std::vector<int> argsort_merge(const Series& keys, bool descending) {
    std::vector<int> idx(keys.size());
    std::iota(idx.begin(), idx.end(), 0);
    if (descending)
        daa::merge_sort(idx, [&](int a, int b) { return keys[static_cast<std::size_t>(a)] > keys[static_cast<std::size_t>(b)]; });
    else
        daa::merge_sort(idx, [&](int a, int b) { return keys[static_cast<std::size_t>(a)] < keys[static_cast<std::size_t>(b)]; });
    return idx;
}

std::vector<int> argsort_quick(const Series& keys, bool descending, const std::string& pivot, std::uint64_t seed) {
    std::vector<int> idx(keys.size());
    std::iota(idx.begin(), idx.end(), 0);
    daa::Pivot p = pivot == "last" ? daa::Pivot::Last : daa::Pivot::Random;
    // Ties broken by index so the result is deterministic despite quicksort being unstable.
    auto less = [&](int a, int b) {
        double ka = keys[static_cast<std::size_t>(a)], kb = keys[static_cast<std::size_t>(b)];
        if (ka != kb) return descending ? ka > kb : ka < kb;
        return a < b;
    };
    daa::quicksort(idx, less, p, seed);
    return idx;
}

Series field(const py::dict& d, const char* key) {
    if (!d.contains(key)) throw std::invalid_argument(std::string("missing input '") + key + "'");
    return to_series(d[key].cast<InArray>());
}

daa::Weights to_weights(const std::vector<double>& w) {
    if (w.size() != 5) throw std::invalid_argument("weights must have 5 values");
    return {w[0], w[1], w[2], w[3], w[4]};
}

daa::Thresholds to_thresholds(const py::dict& t) {
    daa::Thresholds th;
    if (t.contains("z")) th.z = t["z"].cast<double>();
    if (t.contains("p")) th.p = t["p"].cast<double>();
    if (t.contains("est_pct")) th.est_pct = t["est_pct"].cast<double>();
    if (t.contains("dev_pct")) th.dev_pct = t["dev_pct"].cast<double>();
    return th;
}

py::dict day_result(const daa::DayResult& r) {
    py::dict d;
    d["p_trend"] = to_array(r.pct.trend);
    d["p_cons_bull"] = to_array(r.pct.cons_bull);
    d["p_cons_bear"] = to_array(r.pct.cons_bear);
    d["p_rs"] = to_array(r.pct.rs);
    d["p_volume"] = to_array(r.pct.volume);
    d["p_vwap"] = to_array(r.pct.vwap);
    d["flags"] = r.flags;
    d["quadrant"] = r.quadrant;
    d["cls"] = r.cls;
    d["bull_score"] = to_array(r.bull_score);
    d["bear_score"] = to_array(r.bear_score);
    d["bull_order"] = r.bull_order;
    d["bear_order"] = r.bear_order;
    d["bull_cut_est"] = r.bull_cut_est;
    d["bull_cut_dev"] = r.bull_cut_dev;
    d["bear_cut_est"] = r.bear_cut_est;
    d["bear_cut_dev"] = r.bear_cut_dev;
    return d;
}

std::vector<Series> to_rows(const InArray& a) {
    if (a.ndim() != 2) throw std::invalid_argument("expected a 2-D array");
    auto r = a.unchecked<2>();
    std::vector<Series> rows(static_cast<std::size_t>(r.shape(0)), Series(static_cast<std::size_t>(r.shape(1))));
    for (py::ssize_t i = 0; i < r.shape(0); ++i)
        for (py::ssize_t j = 0; j < r.shape(1); ++j) rows[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)] = r(i, j);
    return rows;
}

std::vector<double> to_square(const InArray& a, int* n) {
    if (a.ndim() != 2 || a.shape(0) != a.shape(1)) throw std::invalid_argument("expected a square 2-D array");
    *n = static_cast<int>(a.shape(0));
    auto r = a.unchecked<2>();
    std::vector<double> out(static_cast<std::size_t>(*n) * static_cast<std::size_t>(*n));
    for (py::ssize_t i = 0; i < r.shape(0); ++i)
        for (py::ssize_t j = 0; j < r.shape(1); ++j) out[static_cast<std::size_t>(i * r.shape(1) + j)] = r(i, j);
    return out;
}

py::array_t<double> square_array(const std::vector<double>& v, std::size_t n) {
    py::array_t<double> a({static_cast<py::ssize_t>(n), static_cast<py::ssize_t>(n)});
    std::copy(v.begin(), v.end(), a.mutable_data());
    return a;
}

py::dict tree_dict(const daa::SpanningTree& t, double millis) {
    py::list edges;
    for (const auto& e : t.edges) edges.append(py::make_tuple(e.u, e.v, e.w));
    py::dict d;
    d["edges"] = edges;
    d["total"] = t.total;
    d["ops"] = t.ops;
    d["millis"] = millis;
    return d;
}

template <class F>
py::dict timed_tree(F f) {
    auto t0 = std::chrono::steady_clock::now();
    daa::SpanningTree t = f();
    double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
    return tree_dict(t, ms);
}

}  // namespace

PYBIND11_MODULE(daa_core, m) {
    m.doc() = "DAA course project: algorithm library (C++)";
    m.def("version", [] { return std::string(daa::kVersion); });

    // ---- Unit I: binary search
    m.def("date_range", &daa::date_range, py::arg("dates"), py::arg("start"), py::arg("end"),
          "Index range [first, last) of sorted ISO dates within [start, end].");
    m.def("last_at_or_before", &daa::last_at_or_before, py::arg("dates"), py::arg("date"));
    m.def("prefix_range", &daa::prefix_range, py::arg("sorted"), py::arg("prefix"));
    m.def("lower_bound", [](const Series& a, double x) { return daa::lower_bound_idx(a, x); });
    m.def("upper_bound", [](const Series& a, double x) { return daa::upper_bound_idx(a, x); });

    // ---- Unit I: topological sort
    m.def("topological_sort", &daa::topological_sort, py::arg("n"), py::arg("edges"));

    // ---- Unit II: sorting and inversions
    m.def("merge_sort", [](Series a) { daa::merge_sort(a); return a; });
    m.def("quicksort", [](Series a, const std::string& pivot, std::uint64_t seed) {
        daa::quicksort(a, pivot == "last" ? daa::Pivot::Last : daa::Pivot::Random, seed);
        return a;
    }, py::arg("values"), py::arg("pivot") = "random", py::arg("seed") = 42);
    m.def("argsort_merge", [](const InArray& keys, bool descending) { return argsort_merge(to_series(keys), descending); },
          py::arg("keys"), py::arg("descending") = false);
    m.def("argsort_quick", [](const InArray& keys, bool descending, const std::string& pivot, std::uint64_t seed) {
        return argsort_quick(to_series(keys), descending, pivot, seed);
    }, py::arg("keys"), py::arg("descending") = false, py::arg("pivot") = "random", py::arg("seed") = 42);
    m.def("count_inversions", [](const InArray& a) { return daa::count_inversions(to_series(a)); });
    m.def("count_inversions_naive", [](const InArray& a) { return daa::count_inversions_naive(to_series(a)); });
    m.def("ranking_distance", &daa::ranking_distance, py::arg("before"), py::arg("after"));

    // ---- Trend tests
    m.def("mann_kendall", [](const InArray& a) {
        auto r = daa::mann_kendall(to_series(a));
        py::dict d;
        d["s"] = r.s; d["var"] = r.var; d["z"] = r.z;
        d["concordant"] = r.concordant; d["discordant"] = r.discordant; d["ties"] = r.ties;
        return d;
    });
    m.def("lis_length", [](const InArray& a) { return daa::lis_length(to_series(a)); });
    m.def("lds_length", [](const InArray& a) { return daa::lds_length(to_series(a)); });
    m.def("lis_length_dp", [](const InArray& a) { return daa::lis_length_dp(to_series(a)); });
    m.def("binomial_table", &daa::binomial_table, py::arg("max_n"));
    m.def("sign_test_p", &daa::sign_test_p, py::arg("k"), py::arg("n"));
    m.def("rolling_trend", [](const InArray& close, int window) {
        auto r = daa::rolling_trend(to_series(close), window);
        py::dict d;
        d["mk_s"] = to_array(r.mk_s); d["mk_z"] = to_array(r.mk_z);
        d["lis_ratio"] = to_array(r.lis_ratio); d["lds_ratio"] = to_array(r.lds_ratio);
        d["up_days"] = to_array(r.up_days); d["down_days"] = to_array(r.down_days);
        d["sign_p_up"] = to_array(r.sign_p_up); d["sign_p_down"] = to_array(r.sign_p_down);
        return d;
    }, py::arg("close"), py::arg("window"));

    // ---- Indicators (sliding windows, prefix sums)
    m.def("ema", [](const InArray& x, int n) { return to_array(daa::ema(to_series(x), n)); });
    m.def("rsi_wilder", [](const InArray& x, int n) { return to_array(daa::rsi_wilder(to_series(x), n)); });
    m.def("true_range", [](const InArray& h, const InArray& l, const InArray& c) {
        return to_array(daa::true_range(to_series(h), to_series(l), to_series(c)));
    });
    m.def("atr_wilder", [](const InArray& tr, int n) { return to_array(daa::atr_wilder(to_series(tr), n)); });
    m.def("relative_volume", [](const InArray& v, int n) { return to_array(daa::relative_volume(to_series(v), n)); });
    m.def("rolling_vwap", [](const InArray& p, const InArray& v, int n) {
        return to_array(daa::rolling_vwap(to_series(p), to_series(v), n));
    });
    m.def("rolling_max_prev", [](const InArray& x, int n) { return to_array(daa::rolling_max_prev(to_series(x), n)); });
    m.def("rolling_min_prev", [](const InArray& x, int n) { return to_array(daa::rolling_min_prev(to_series(x), n)); });
    m.def("spike_flags", [](const InArray& x, int n, double k) { return to_array(daa::spike_flags(to_series(x), n, k)); });

    // ---- Classification and ranking
    m.def("percentile_ranks", [](const InArray& x) { return to_array(daa::percentile_ranks(to_series(x))); });
    m.def("percentile_cutoff", [](const InArray& x, double pct) { return daa::percentile_cutoff(to_series(x), pct); });
    m.def("classify_day", [](const py::dict& in, const std::vector<double>& weights, const py::dict& thresholds) {
        daa::DayInputs di{field(in, "close"), field(in, "ema50"), field(in, "ema200"), field(in, "high20"),
                          field(in, "low20"), field(in, "mk_z20"), field(in, "mk_z60"), field(in, "lis_ratio60"),
                          field(in, "lds_ratio60"), field(in, "sign_p_up60"), field(in, "sign_p_down60"),
                          field(in, "rs60"), field(in, "updown_vol20"), field(in, "vwap_dist"), field(in, "ret5"),
                          field(in, "rvol5_avg")};
        return day_result(daa::classify_day(di, to_weights(weights), to_thresholds(thresholds)));
    }, py::arg("inputs"), py::arg("weights") = std::vector<double>{1, 1, 1, 1, 1},
       py::arg("thresholds") = py::dict());
    m.def("rescore_day", [](const py::dict& pct, const std::vector<int>& flags, const std::vector<int>& quadrant,
                            const std::vector<double>& weights, const py::dict& thresholds) {
        daa::Percentiles p{field(pct, "p_trend"), field(pct, "p_cons_bull"), field(pct, "p_cons_bear"),
                           field(pct, "p_rs"), field(pct, "p_volume"), field(pct, "p_vwap")};
        return day_result(daa::rescore_day(p, flags, quadrant, to_weights(weights), to_thresholds(thresholds)));
    }, py::arg("percentiles"), py::arg("flags"), py::arg("quadrant"), py::arg("weights"),
       py::arg("thresholds") = py::dict());

    // ---- Correlation network (MST: Prim, Kruskal; components: BFS, DFS)
    m.def("correlation_matrix", [](const InArray& closes) {
        auto rows = to_rows(closes);
        std::vector<double> rho;
        {
            py::gil_scoped_release release;
            rho = daa::correlation_matrix(rows);
        }
        return square_array(rho, rows.size());
    }, py::arg("closes"), "Correlation matrix of daily log returns; closes is N x L.");
    m.def("correlation_distance", [](const InArray& rho) {
        int n = 0;
        auto v = to_square(rho, &n);
        return square_array(daa::correlation_distance(v), static_cast<std::size_t>(n));
    });
    m.def("prim_mst", [](const InArray& dist) {
        int n = 0;
        auto v = to_square(dist, &n);
        return timed_tree([&] { return daa::prim_mst(v, n); });
    });
    m.def("kruskal_mst", [](const InArray& dist) {
        int n = 0;
        auto v = to_square(dist, &n);
        return timed_tree([&] { return daa::kruskal_mst(v, n); });
    });
    m.def("threshold_components", [](const InArray& rho, double threshold) {
        int n = 0;
        auto v = to_square(rho, &n);
        auto adj = daa::threshold_graph(v, n, threshold);
        std::size_t edges = 0;
        for (const auto& a : adj) edges += a.size();
        py::dict d;
        d["bfs"] = daa::components_bfs(adj);
        d["dfs"] = daa::components_dfs(adj);
        d["edges"] = edges / 2;
        return d;
    }, py::arg("rho"), py::arg("threshold"));

    // ---- Portfolio: tree DP, knapsacks, subset sum, coin change
    m.def("tree_max_independent_set", [](int n, const std::vector<std::pair<int, int>>& edges,
                                         const std::vector<double>& weight) {
        auto r = daa::tree_max_independent_set(n, edges, weight);
        py::dict d;
        d["nodes"] = r.nodes;
        d["weight"] = r.weight;
        return d;
    }, py::arg("n"), py::arg("edges"), py::arg("weight"));
    m.def("fractional_knapsack", [](const std::vector<double>& value, const std::vector<double>& weight, double cap) {
        auto r = daa::fractional_knapsack(value, weight, cap);
        py::dict d;
        d["fraction"] = r.fraction;
        d["value"] = r.value;
        d["used"] = r.used;
        return d;
    }, py::arg("value"), py::arg("weight"), py::arg("capacity"));
    m.def("knapsack_01", [](const std::vector<double>& value, const std::vector<long long>& weight, long long cap) {
        daa::Knapsack01Result r;
        {
            py::gil_scoped_release release;
            r = daa::knapsack_01(value, weight, cap);
        }
        py::dict d;
        d["items"] = r.items;
        d["value"] = r.value;
        d["used"] = r.used;
        d["cells"] = r.cells;
        return d;
    }, py::arg("value"), py::arg("weight"), py::arg("capacity"));
    auto subset = [](bool brute, const std::vector<double>& cost, const std::vector<double>& score,
                     const std::vector<int>& group, double capacity, double target_frac, int max_items,
                     int max_per_group) {
        daa::SubsetProblem p{cost, score, group, capacity, target_frac, max_items, max_per_group};
        daa::SubsetResult r;
        {
            py::gil_scoped_release release;
            r = brute ? daa::subset_sum_brute_force(p) : daa::subset_sum_backtracking(p);
        }
        py::dict d;
        d["items"] = r.items;
        d["cost"] = r.cost;
        d["score"] = r.score;
        d["reached_target"] = r.reached_target;
        d["nodes"] = r.nodes;
        return d;
    };
    m.def("subset_sum_backtracking", [subset](const std::vector<double>& cost, const std::vector<double>& score,
                                              const std::vector<int>& group, double capacity, double target_frac,
                                              int max_items, int max_per_group) {
        return subset(false, cost, score, group, capacity, target_frac, max_items, max_per_group);
    }, py::arg("cost"), py::arg("score"), py::arg("group"), py::arg("capacity"), py::arg("target_frac") = 0.95,
       py::arg("max_items") = 10, py::arg("max_per_group") = 2);
    m.def("subset_sum_brute_force", [subset](const std::vector<double>& cost, const std::vector<double>& score,
                                             const std::vector<int>& group, double capacity, double target_frac,
                                             int max_items, int max_per_group) {
        return subset(true, cost, score, group, capacity, target_frac, max_items, max_per_group);
    }, py::arg("cost"), py::arg("score"), py::arg("group"), py::arg("capacity"), py::arg("target_frac") = 0.95,
       py::arg("max_items") = 10, py::arg("max_per_group") = 2);
    m.def("coin_change_max_spend", [](const std::vector<long long>& price, long long amount) {
        auto r = daa::coin_change_max_spend(price, amount);
        py::dict d;
        d["count"] = r.count;
        d["spent"] = r.spent;
        return d;
    }, py::arg("price"), py::arg("amount"));

    // ---- Backtest: exits, interval scheduling, hindsight longest path
    m.def("simulate_exits", [](const InArray& open, const InArray& high, const InArray& low, const InArray& close,
                               const std::vector<int>& bullish, const std::vector<int>& entries,
                               const std::vector<double>& entry_atr, int hold, double stop_atr) {
        auto x = daa::simulate_exits(to_series(open), to_series(high), to_series(low), to_series(close), bullish,
                                     entries, entry_atr, hold, stop_atr);
        std::vector<int> idx, reason;
        std::vector<double> price;
        for (const auto& e : x) {
            idx.push_back(e.exit_index);
            price.push_back(e.exit_price);
            reason.push_back(e.reason);
        }
        py::dict d;
        d["exit_index"] = idx;
        d["exit_price"] = price;
        d["reason"] = reason;
        return d;
    }, py::arg("open"), py::arg("high"), py::arg("low"), py::arg("close"), py::arg("bullish"), py::arg("entries"),
       py::arg("entry_atr"), py::arg("hold"), py::arg("stop_atr"));
    m.def("interval_scheduling", &daa::interval_scheduling, py::arg("start"), py::arg("end"));
    m.def("hindsight_longest_path", [](const InArray& closes, int max_hold, double cost_per_side) {
        auto rows = to_rows(closes);
        daa::HindsightPath r;
        {
            py::gil_scoped_release release;
            r = daa::hindsight_longest_path(rows, max_hold, cost_per_side);
        }
        py::dict d;
        d["total_log_return"] = r.total_log_return;
        d["buy_day"] = r.buy_day;
        d["sell_day"] = r.sell_day;
        d["stock"] = r.stock;
        return d;
    }, py::arg("closes"), py::arg("max_hold"), py::arg("cost_per_side"));

    // ---- Algorithm Lab
    m.def("benchmark_names", &daa::benchmark_names);
    m.def("run_benchmark", [](const std::string& name, long long n, const std::string& input, std::uint64_t seed,
                              int repeats) {
        daa::BenchResult r;
        {
            py::gil_scoped_release release;
            r = daa::run_benchmark(name, n, input, seed, repeats);
        }
        return py::make_tuple(r.millis, r.ops);
    }, py::arg("name"), py::arg("n"), py::arg("input") = "random", py::arg("seed") = 1, py::arg("repeats") = 3);

    // ---- Feature engine
    m.def("feature_inputs", &daa::feature_inputs);
    m.def("feature_edges", &daa::feature_edges);
    m.def("feature_order", &daa::feature_order);
    m.def("compute_features", [](const InArray& open, const InArray& high, const InArray& low, const InArray& close,
                                 const InArray& volume, const InArray& index_close) {
        daa::Bars b{to_series(open), to_series(high), to_series(low), to_series(close), to_series(volume),
                    to_series(index_close)};
        daa::FeatureMap f;
        {
            py::gil_scoped_release release;
            f = daa::compute_features(b);
        }
        return feature_dict(f);
    }, py::arg("open"), py::arg("high"), py::arg("low"), py::arg("close"), py::arg("volume"), py::arg("index_close"));
}
