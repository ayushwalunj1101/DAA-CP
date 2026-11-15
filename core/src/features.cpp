#include "daa/features.hpp"

#include <functional>
#include <stdexcept>
#include <unordered_map>

#include "daa/indicators.hpp"
#include "daa/topo.hpp"

namespace daa {

namespace {

struct Node {
    std::string name;
    std::vector<std::string> deps;
    std::function<Series(const FeatureMap&)> compute;
};

// Registered deliberately out of dependency order: the engine must not rely on registration order.
const std::vector<Node>& registry() {
    static const std::vector<Node> nodes = {
        {"rs60", {"ret60", "index_ret60"},
         [](const FeatureMap& f) {
             const Series &a = f.at("ret60"), &b = f.at("index_ret60");
             Series out(a.size(), kNaN);
             for (std::size_t i = 0; i < a.size(); ++i)
                 if (!is_nan(a[i]) && !is_nan(b[i])) out[i] = a[i] - b[i];
             return out;
         }},
        {"vwap_dist", {"close", "vwap20", "atr14"},
         [](const FeatureMap& f) {
             const Series &c = f.at("close"), &v = f.at("vwap20"), &a = f.at("atr14");
             Series out(c.size(), kNaN);
             for (std::size_t i = 0; i < c.size(); ++i)
                 if (!is_nan(v[i]) && !is_nan(a[i]) && a[i] > 0) out[i] = (c[i] - v[i]) / a[i];
             return out;
         }},
        {"atr14", {"true_range"}, [](const FeatureMap& f) { return atr_wilder(f.at("true_range"), 14); }},
        {"true_range", {"high", "low", "close"},
         [](const FeatureMap& f) { return true_range(f.at("high"), f.at("low"), f.at("close")); }},
        {"typical_price", {"high", "low", "close"},
         [](const FeatureMap& f) {
             const Series &h = f.at("high"), &l = f.at("low"), &c = f.at("close");
             Series out(c.size());
             for (std::size_t i = 0; i < c.size(); ++i) out[i] = (h[i] + l[i] + c[i]) / 3.0;
             return out;
         }},
        {"vwap20", {"typical_price", "volume"},
         [](const FeatureMap& f) { return rolling_vwap(f.at("typical_price"), f.at("volume"), 20); }},
        {"ema20", {"close"}, [](const FeatureMap& f) { return ema(f.at("close"), 20); }},
        {"ema50", {"close"}, [](const FeatureMap& f) { return ema(f.at("close"), 50); }},
        {"ema200", {"close"}, [](const FeatureMap& f) { return ema(f.at("close"), 200); }},
        {"rsi14", {"close"}, [](const FeatureMap& f) { return rsi_wilder(f.at("close"), 14); }},
        {"rvol20", {"volume"}, [](const FeatureMap& f) { return relative_volume(f.at("volume"), 20); }},
        {"rvol5_avg", {"rvol20"}, [](const FeatureMap& f) { return rolling_mean(f.at("rvol20"), 5); }},
        {"updown_vol20", {"close", "rvol20"},
         [](const FeatureMap& f) { return up_down_volume_ratio(f.at("close"), f.at("rvol20"), 20); }},
        {"high20", {"high"}, [](const FeatureMap& f) { return rolling_max_prev(f.at("high"), 20); }},
        {"low20", {"low"}, [](const FeatureMap& f) { return rolling_min_prev(f.at("low"), 20); }},
        {"ret5", {"close"}, [](const FeatureMap& f) { return pct_change(f.at("close"), 5); }},
        {"ret1", {"close"}, [](const FeatureMap& f) { return pct_change(f.at("close"), 1); }},
        {"ret60", {"close"}, [](const FeatureMap& f) { return log_change(f.at("close"), 60); }},
        {"index_ret60", {"index_close"}, [](const FeatureMap& f) { return log_change(f.at("index_close"), 60); }},
        {"vol_spike", {"volume"}, [](const FeatureMap& f) { return spike_flags(f.at("volume"), 60, 3.0); }},
    };
    return nodes;
}

struct Graph {
    std::vector<std::string> names;  // inputs first, then registry nodes
    std::unordered_map<std::string, int> id;
    std::vector<std::pair<int, int>> edges;
};

const Graph& graph() {
    static const Graph g = [] {
        Graph g;
        for (const auto& in : feature_inputs()) {
            g.id[in] = static_cast<int>(g.names.size());
            g.names.push_back(in);
        }
        for (const auto& node : registry()) {
            if (g.id.count(node.name)) throw std::logic_error("duplicate feature " + node.name);
            g.id[node.name] = static_cast<int>(g.names.size());
            g.names.push_back(node.name);
        }
        for (const auto& node : registry())
            for (const auto& dep : node.deps) {
                auto it = g.id.find(dep);
                if (it == g.id.end()) throw std::logic_error(node.name + " depends on unknown feature " + dep);
                g.edges.push_back({it->second, g.id.at(node.name)});
            }
        return g;
    }();
    return g;
}

}  // namespace

std::vector<std::string> feature_inputs() { return {"open", "high", "low", "close", "volume", "index_close"}; }

std::vector<std::pair<std::string, std::string>> feature_edges() {
    const Graph& g = graph();
    std::vector<std::pair<std::string, std::string>> out;
    for (const auto& [u, v] : g.edges)
        out.push_back({g.names[static_cast<std::size_t>(u)], g.names[static_cast<std::size_t>(v)]});
    return out;
}

std::vector<std::string> feature_order() {
    const Graph& g = graph();
    std::vector<std::string> out;
    const std::size_t inputs = feature_inputs().size();
    for (int v : topological_sort(static_cast<int>(g.names.size()), g.edges))
        if (static_cast<std::size_t>(v) >= inputs) out.push_back(g.names[static_cast<std::size_t>(v)]);
    return out;
}

FeatureMap compute_features(const Bars& b) {
    const std::size_t n = b.close.size();
    for (const Series* s : {&b.open, &b.high, &b.low, &b.volume, &b.index_close})
        if (s->size() != n) throw std::invalid_argument("all input series must have the same length");
    FeatureMap f{{"open", b.open},   {"high", b.high},     {"low", b.low},
                 {"close", b.close}, {"volume", b.volume}, {"index_close", b.index_close}};
    std::unordered_map<std::string, const Node*> by_name;
    for (const auto& node : registry()) by_name[node.name] = &node;
    for (const auto& name : feature_order()) f[name] = by_name.at(name)->compute(f);
    return f;
}

}  // namespace daa
