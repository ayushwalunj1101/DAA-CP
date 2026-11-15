#pragma once
// Feature engine: every indicator is a node in a dependency graph; topological sort fixes the
// order of computation, and a cycle (a mis-specified dependency) is reported instead of computed.
#include <map>
#include <string>
#include <utility>
#include <vector>

#include "daa/common.hpp"

namespace daa {

struct Bars {
    Series open, high, low, close, volume, index_close;  // index_close aligned to the stock's dates
};

using FeatureMap = std::map<std::string, Series>;

// Names of the input series every computation starts from.
std::vector<std::string> feature_inputs();

// Dependency edges (dependency -> feature) of the feature graph.
std::vector<std::pair<std::string, std::string>> feature_edges();

// Feature names in the order the engine computes them (a topological order of the graph).
std::vector<std::string> feature_order();

// Computes every feature for one stock. Returns inputs and features, all of the same length.
FeatureMap compute_features(const Bars& bars);

}  // namespace daa
