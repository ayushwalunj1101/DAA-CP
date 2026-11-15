#include "daa/topo.hpp"

#include <algorithm>
#include <stdexcept>
#include <string>

namespace daa {

namespace {
enum class Color { White, Gray, Black };
}

std::vector<int> topological_sort(int n, const std::vector<std::pair<int, int>>& edges) {
    if (n < 0) throw std::invalid_argument("negative node count");
    std::vector<std::vector<int>> adj(static_cast<std::size_t>(n));
    for (const auto& [u, v] : edges) {
        if (u < 0 || v < 0 || u >= n || v >= n) throw std::invalid_argument("edge endpoint out of range");
        adj[static_cast<std::size_t>(u)].push_back(v);
    }
    std::vector<Color> color(static_cast<std::size_t>(n), Color::White);
    std::vector<int> finished;
    finished.reserve(static_cast<std::size_t>(n));

    // Iterative DFS (explicit stack of (node, next-neighbour index)) so deep chains cannot overflow.
    for (int s = 0; s < n; ++s) {
        if (color[static_cast<std::size_t>(s)] != Color::White) continue;
        std::vector<std::pair<int, std::size_t>> stack{{s, 0}};
        color[static_cast<std::size_t>(s)] = Color::Gray;
        while (!stack.empty()) {
            auto& [u, next] = stack.back();
            const auto& nbrs = adj[static_cast<std::size_t>(u)];
            if (next < nbrs.size()) {
                int v = nbrs[next++];
                Color c = color[static_cast<std::size_t>(v)];
                if (c == Color::Gray)
                    throw std::invalid_argument("cycle detected at node " + std::to_string(v));
                if (c == Color::White) {
                    color[static_cast<std::size_t>(v)] = Color::Gray;
                    stack.push_back({v, 0});
                }
            } else {
                color[static_cast<std::size_t>(u)] = Color::Black;
                finished.push_back(u);
                stack.pop_back();
            }
        }
    }
    std::reverse(finished.begin(), finished.end());
    return finished;
}

}  // namespace daa
