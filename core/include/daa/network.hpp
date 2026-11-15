#pragma once
// Correlation network: Pearson correlations, distance d = sqrt(2(1 - rho)), minimum spanning tree
// (Prim and Kruskal, Unit IV greedy) and connected components of the threshold graph (Unit I BFS/DFS).
#include <cstdint>
#include <vector>

#include "daa/common.hpp"

namespace daa {

// closes: N series of equal length L (L >= 3). Returns the N x N correlation matrix (row-major) of
// their daily log returns. O(N^2 L).
std::vector<double> correlation_matrix(const std::vector<Series>& closes);

// Element-wise d = sqrt(2 (1 - rho)), a metric: 0 for identical moves, 2 for opposite moves.
std::vector<double> correlation_distance(const std::vector<double>& rho);

struct WeightedEdge {
    int u, v;
    double w;
};

struct SpanningTree {
    std::vector<WeightedEdge> edges;  // n - 1 edges when the graph is connected
    double total = 0;
    std::uint64_t ops = 0;  // comparisons / relaxations, for the Algorithm Lab
};

// Prim's algorithm on a dense graph (adjacency matrix): O(V^2), no heap needed.
// Cut property: the lightest edge leaving the current tree belongs to some MST.
SpanningTree prim_mst(const std::vector<double>& dist, int n);

// Kruskal's algorithm: sort all edges (merge sort, O(E log E)) and add each edge that joins two
// different components of a union-find structure (path compression + union by rank).
SpanningTree kruskal_mst(const std::vector<double>& dist, int n);

// Adjacency lists of the graph with an edge wherever rho >= threshold (no self loops).
std::vector<std::vector<int>> threshold_graph(const std::vector<double>& rho, int n, double threshold);

// Component label of every node (labels 0, 1, ... in order of the smallest node), O(V + E).
std::vector<int> components_bfs(const std::vector<std::vector<int>>& adj);
std::vector<int> components_dfs(const std::vector<std::vector<int>>& adj);

}  // namespace daa
