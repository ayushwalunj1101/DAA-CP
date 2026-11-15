#pragma once
// Trend tests: Mann-Kendall (via inversion counting), LIS consistency (DP), binomial sign test (Pascal DP).
#include <cstddef>
#include <vector>

#include "daa/common.hpp"

namespace daa {

struct MannKendall {
    double s = 0;      // concordant - discordant pairs
    double var = 0;    // variance of S under no trend, tie-corrected
    double z = 0;      // continuity-corrected normal score
    long long concordant = 0, discordant = 0, ties = 0;
};

// O(n log n): discordant pairs = inversions (merge sort); ties from sorted groups; concordant = rest.
MannKendall mann_kendall(const std::vector<double>& x);

// Longest strictly increasing / decreasing subsequence length in O(n log n) (patience method:
// tails[k] = smallest tail of an increasing subsequence of length k + 1, found by binary search).
std::size_t lis_length(const std::vector<double>& x, OpCounter* ops = nullptr);
std::size_t lds_length(const std::vector<double>& x);

// O(n^2) dynamic program: L[i] = 1 + max L[j] over j < i with x[j] < x[i].
std::size_t lis_length_dp(const std::vector<double>& x, OpCounter* ops = nullptr);

// Pascal's triangle C[n][k] for 0 <= k <= n <= max_n (max_n <= 62 so values fit in 64 bits).
std::vector<std::vector<unsigned long long>> binomial_table(int max_n);

// One-sided sign test: P(X >= k) for X ~ Binomial(n, 1/2).
double sign_test_p(int k, int n);

struct RollingTrend {
    Series mk_s, mk_z, lis_ratio, lds_ratio, up_days, down_days, sign_p_up, sign_p_down;
};

// For every day t >= window: Mann-Kendall and LIS/LDS ratios over the last `window` closes, and sign
// tests over the last `window` daily changes (flat days excluded). Earlier days are NaN.
RollingTrend rolling_trend(const Series& close, int window);

}  // namespace daa
