#include "daa/portfolio.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <stdexcept>

#include "daa/sorting.hpp"

namespace daa {

IndependentSet tree_max_independent_set(int n, const std::vector<std::pair<int, int>>& edges,
                                        const std::vector<double>& weight) {
    if (n < 0 || weight.size() != static_cast<std::size_t>(n)) throw std::invalid_argument("weight size must be n");
    const std::size_t N = static_cast<std::size_t>(n);
    std::vector<std::vector<int>> adj(N);
    for (const auto& [u, v] : edges) {
        if (u < 0 || v < 0 || u >= n || v >= n) throw std::invalid_argument("edge endpoint out of range");
        adj[static_cast<std::size_t>(u)].push_back(v);
        adj[static_cast<std::size_t>(v)].push_back(u);
    }
    std::vector<double> incl(N, 0), excl(N, 0);
    std::vector<int> parent(N, -2), order;  // -2 = unvisited
    order.reserve(N);
    // Iterative DFS from every unvisited node (the input may be a forest); `order` is a pre-order.
    for (std::size_t root = 0; root < N; ++root) {
        if (parent[root] != -2) continue;
        parent[root] = -1;
        std::vector<int> stack{static_cast<int>(root)};
        while (!stack.empty()) {
            int u = stack.back();
            stack.pop_back();
            order.push_back(u);
            for (int v : adj[static_cast<std::size_t>(u)])
                if (parent[static_cast<std::size_t>(v)] == -2) {
                    parent[static_cast<std::size_t>(v)] = u;
                    stack.push_back(v);
                } else if (v != parent[static_cast<std::size_t>(u)]) {
                    throw std::invalid_argument("edges contain a cycle; expected a forest");
                }
        }
    }
    // Reverse pre-order visits children before parents: fill the DP bottom-up.
    for (auto it = order.rbegin(); it != order.rend(); ++it) {
        std::size_t u = static_cast<std::size_t>(*it);
        incl[u] += weight[u];
        int p = parent[u];
        if (p >= 0) {
            incl[static_cast<std::size_t>(p)] += excl[u];
            excl[static_cast<std::size_t>(p)] += std::fmax(incl[u], excl[u]);
        }
    }
    // Top-down reconstruction: a node is taken if its parent is not and including it is at least as good.
    IndependentSet r;
    std::vector<char> taken(N, 0);
    for (int u : order) {
        std::size_t uu = static_cast<std::size_t>(u);
        int p = parent[uu];
        bool parent_taken = p >= 0 && taken[static_cast<std::size_t>(p)];
        taken[uu] = !parent_taken && incl[uu] > excl[uu];
        if (p < 0) r.weight += std::fmax(incl[uu], excl[uu]);
    }
    for (std::size_t u = 0; u < N; ++u)
        if (taken[u]) r.nodes.push_back(static_cast<int>(u));
    return r;
}

FractionalResult fractional_knapsack(const std::vector<double>& value, const std::vector<double>& weight,
                                     double capacity) {
    if (value.size() != weight.size()) throw std::invalid_argument("value and weight sizes differ");
    FractionalResult r;
    r.fraction.assign(value.size(), 0.0);
    std::vector<int> idx(value.size());
    std::iota(idx.begin(), idx.end(), 0);
    auto ratio = [&](int i) {
        double w = weight[static_cast<std::size_t>(i)];
        return w > 0 ? value[static_cast<std::size_t>(i)] / w : INFINITY;
    };
    merge_sort(idx, [&](int a, int b) { return ratio(a) > ratio(b); });  // best value per rupee first
    double left = capacity;
    for (int i : idx) {
        std::size_t k = static_cast<std::size_t>(i);
        if (left <= 0) break;
        if (value[k] <= 0) continue;
        double take = weight[k] <= left ? 1.0 : left / weight[k];
        r.fraction[k] = take;
        r.value += take * value[k];
        r.used += take * weight[k];
        left -= take * weight[k];
    }
    return r;
}

Knapsack01Result knapsack_01(const std::vector<double>& value, const std::vector<long long>& weight,
                             long long capacity) {
    if (value.size() != weight.size()) throw std::invalid_argument("value and weight sizes differ");
    if (capacity < 0) throw std::invalid_argument("capacity must be non-negative");
    const std::size_t n = value.size(), W = static_cast<std::size_t>(capacity);
    if ((n + 1) * (W + 1) > 200'000'000ULL) throw std::invalid_argument("knapsack table too large; use coarser units");
    // best[i][c] = best value using the first i items with capacity c.
    std::vector<std::vector<double>> best(n + 1, std::vector<double>(W + 1, 0.0));
    for (std::size_t i = 1; i <= n; ++i) {
        const long long w = weight[i - 1];
        if (w < 0) throw std::invalid_argument("weights must be non-negative");
        for (std::size_t c = 0; c <= W; ++c) {
            best[i][c] = best[i - 1][c];
            if (static_cast<long long>(c) >= w) {
                double with = best[i - 1][c - static_cast<std::size_t>(w)] + value[i - 1];
                if (with > best[i][c]) best[i][c] = with;
            }
        }
    }
    Knapsack01Result r;
    r.cells = static_cast<std::uint64_t>((n + 1) * (W + 1));
    r.value = best[n][W];
    std::size_t c = W;
    for (std::size_t i = n; i >= 1; --i) {
        if (best[i][c] != best[i - 1][c]) {  // item i - 1 was taken
            r.items.push_back(static_cast<int>(i - 1));
            c -= static_cast<std::size_t>(weight[i - 1]);
            r.used += weight[i - 1];
        }
    }
    std::reverse(r.items.begin(), r.items.end());
    return r;
}

namespace {

struct Search {
    const SubsetProblem& p;
    bool use_target_prune;
    bool prune;
    std::vector<int> pick, group_count;
    std::vector<double> suffix_cost;  // total cost of items i..n-1
    SubsetResult best;
    bool have_best = false;

    Search(const SubsetProblem& prob, bool target_prune, bool with_pruning)
        : p(prob), use_target_prune(target_prune), prune(with_pruning) {
        int groups = 0;
        for (int g : p.group) groups = std::max(groups, g + 1);
        group_count.assign(static_cast<std::size_t>(groups), 0);
        suffix_cost.assign(p.cost.size() + 1, 0.0);
        for (std::size_t i = p.cost.size(); i-- > 0;) suffix_cost[i] = suffix_cost[i + 1] + p.cost[i];
    }

    bool feasible_limits(int count) const {
        if (count > p.max_items) return false;
        for (int c : group_count)
            if (c > p.max_per_group) return false;
        return true;
    }

    void consider(double cost, double score) {
        const double target = p.target_frac * p.capacity;
        const bool reached = cost >= target - 1e-9;
        bool better;
        if (!have_best)
            better = true;
        else if (reached != best.reached_target)
            better = reached;
        else if (reached)
            better = score > best.score + 1e-12 || (std::fabs(score - best.score) <= 1e-12 && cost > best.cost);
        else
            better = cost > best.cost + 1e-9 || (std::fabs(cost - best.cost) <= 1e-9 && score > best.score);
        if (better) {
            have_best = true;
            best.items = pick;
            best.cost = cost;
            best.score = score;
            best.reached_target = reached;
        }
    }

    void run(std::size_t i, double cost, double score) {
        ++best.nodes;
        const int count = static_cast<int>(pick.size());
        if (prune) {
            if (cost > p.capacity + 1e-9 || !feasible_limits(count)) return;
            if (use_target_prune && cost + suffix_cost[i] < p.target_frac * p.capacity - 1e-9) return;
        }
        if (i == p.cost.size()) {
            if (cost <= p.capacity + 1e-9 && feasible_limits(count)) consider(cost, score);
            return;
        }
        // Branch 1: take item i.
        pick.push_back(static_cast<int>(i));
        ++group_count[static_cast<std::size_t>(p.group[i])];
        run(i + 1, cost + p.cost[i], score + p.score[i]);
        --group_count[static_cast<std::size_t>(p.group[i])];
        pick.pop_back();
        // Branch 2: skip item i.
        run(i + 1, cost, score);
    }
};

void check_problem(const SubsetProblem& p) {
    const std::size_t n = p.cost.size();
    if (p.score.size() != n || p.group.size() != n) throw std::invalid_argument("cost, score and group sizes differ");
    if (n > 40) throw std::invalid_argument("at most 40 items");
    for (int g : p.group)
        if (g < 0) throw std::invalid_argument("group ids must be non-negative");
}

}  // namespace

SubsetResult subset_sum_backtracking(const SubsetProblem& p) {
    check_problem(p);
    Search target(p, true, true);  // pass 1: only subsets that can still reach the target
    target.run(0, 0, 0);
    if (target.have_best && target.best.reached_target) return target.best;
    Search fallback(p, false, true);  // pass 2: nothing reaches the target; spend as much as possible
    fallback.run(0, 0, 0);
    fallback.best.nodes += target.best.nodes;
    return fallback.best;
}

SubsetResult subset_sum_brute_force(const SubsetProblem& p) {
    check_problem(p);
    if (p.cost.size() > 25) throw std::invalid_argument("brute force supports at most 25 items");
    Search all(p, false, false);
    all.run(0, 0, 0);
    return all.best;
}

CoinChangeResult coin_change_max_spend(const std::vector<long long>& price, long long amount) {
    if (amount < 0) throw std::invalid_argument("amount must be non-negative");
    if (amount > 50'000'000) throw std::invalid_argument("amount too large; use coarser units");
    const std::size_t A = static_cast<std::size_t>(amount);
    std::vector<int> last(A + 1, -1);  // last[x] = price index used to reach x (-1 unreachable), x > 0
    std::vector<char> reach(A + 1, 0);
    reach[0] = 1;
    for (std::size_t x = 1; x <= A; ++x)
        for (std::size_t i = 0; i < price.size(); ++i) {
            long long pr = price[i];
            if (pr > 0 && static_cast<long long>(x) >= pr && reach[x - static_cast<std::size_t>(pr)]) {
                reach[x] = 1;
                last[x] = static_cast<int>(i);
                break;
            }
        }
    CoinChangeResult r;
    r.count.assign(price.size(), 0);
    std::size_t x = A;
    while (!reach[x]) --x;
    r.spent = static_cast<long long>(x);
    while (x > 0) {
        int i = last[x];
        ++r.count[static_cast<std::size_t>(i)];
        x -= static_cast<std::size_t>(price[static_cast<std::size_t>(i)]);
    }
    return r;
}

}  // namespace daa
