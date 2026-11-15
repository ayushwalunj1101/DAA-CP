#pragma once
// Unit I: topological sort by depth-first search.
#include <utility>
#include <vector>

namespace daa {

// Nodes are 0..n-1; an edge (u, v) means u must come before v.
// Returns a topological order in O(V + E). Throws std::invalid_argument if the graph has a cycle.
// Correctness: a node is appended only after every node reachable from it has finished, so
// reversing the finish order places each u before every v with an edge u -> v.
std::vector<int> topological_sort(int n, const std::vector<std::pair<int, int>>& edges);

}  // namespace daa
