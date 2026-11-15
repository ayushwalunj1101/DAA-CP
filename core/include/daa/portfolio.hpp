#pragma once
// Portfolio construction: tree DP (Unit III), fractional knapsack (Unit IV greedy), 0/1 knapsack and
// coin change (Unit III DP), subset sum by backtracking (Unit IV) and brute-force enumeration (Unit II).
#include <cstdint>
#include <utility>
#include <vector>

#include "daa/common.hpp"

namespace daa {

// ---- Maximum-weight independent set on a forest (largest independent set for trees, weighted).
// incl(v) = w(v) + sum excl(c);  excl(v) = sum max(incl(c), excl(c)) over children c.  O(V).
struct IndependentSet {
    std::vector<int> nodes;  // chosen nodes, ascending
    double weight = 0;
};
IndependentSet tree_max_independent_set(int n, const std::vector<std::pair<int, int>>& edges,
                                        const std::vector<double>& weight);

// ---- Fractional knapsack (greedy by value per unit weight; optimal when items are divisible).
struct FractionalResult {
    std::vector<double> fraction;  // 0..1 per item
    double value = 0, used = 0;
};
FractionalResult fractional_knapsack(const std::vector<double>& value, const std::vector<double>& weight,
                                     double capacity);

// ---- 0/1 knapsack by dynamic programming over integer capacities: O(n W) time and space.
struct Knapsack01Result {
    std::vector<int> items;  // chosen item indices, ascending
    double value = 0;
    long long used = 0;
    std::uint64_t cells = 0;  // DP table size, n x (W + 1)
};
Knapsack01Result knapsack_01(const std::vector<double>& value, const std::vector<long long>& weight, long long capacity);

// ---- Subset selection under limits.
struct SubsetProblem {
    std::vector<double> cost, score;
    std::vector<int> group;  // sector id of each item
    double capacity = 0;
    double target_frac = 0.95;  // a subset must spend at least this share of the capacity
    int max_items = 10;
    int max_per_group = 2;
};
struct SubsetResult {
    std::vector<int> items;
    double cost = 0, score = 0;
    bool reached_target = false;
    std::uint64_t nodes = 0;  // recursion nodes visited
};
// Backtracking with pruning: over budget, cannot reach the target any more, or a count/sector limit broken.
// Among subsets reaching the target, the highest total score wins; if none reaches it, the subset that
// spends the most (then scores highest) within the limits is returned.
SubsetResult subset_sum_backtracking(const SubsetProblem& p);
// The same objective by enumerating all 2^n subsets recursively (no pruning).
SubsetResult subset_sum_brute_force(const SubsetProblem& p);

// ---- Coin change: spend as much of `amount` as possible on whole units of the given prices
// (each price usable any number of times). reachable[x] = OR reachable[x - price_i]. O(n * amount).
struct CoinChangeResult {
    std::vector<long long> count;  // units bought of each price
    long long spent = 0;
};
CoinChangeResult coin_change_max_spend(const std::vector<long long>& price, long long amount);

}  // namespace daa
