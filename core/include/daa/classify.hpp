#pragma once
// Daily cross-sectional scoring, classification and ranking of the universe.
#include <array>
#include <vector>

#include "daa/common.hpp"

namespace daa {

enum Cls : int { EST_BEAR = -2, DEV_BEAR = -1, NEUTRAL = 0, DEV_BULL = 1, EST_BULL = 2 };
enum Quadrant : int { Q_NONE = -1, ACCUMULATION = 0, WEAK_RALLY = 1, DISTRIBUTION = 2, WEAK_SELLOFF = 3 };

// Rule flags (bit mask) that do not depend on the score weights.
enum Flag : int { EST_BULL_RULES = 1, DEV_BULL_RULES = 2, EST_BEAR_RULES = 4, DEV_BEAR_RULES = 8 };

// One entry per stock, all series of length N (the stocks in the universe that day).
struct DayInputs {
    Series close, ema50, ema200, high20, low20, mk_z20, mk_z60, lis60, lds60, sign_p_up60, sign_p_down60, rs60,
        updown_vol20, vwap_dist, ret5, rvol5_avg;
};

struct Thresholds {
    double z = 1.96;          // Mann-Kendall significance
    double p = 0.05;          // sign-test significance
    double est_pct = 90.0;    // score percentile for Established
    double dev_pct = 75.0;    // score percentile for Developing
};

// Percentile ranks of the five bullish inputs plus the bearish consistency input (0..100).
struct Percentiles {
    Series trend, cons_bull, cons_bear, rs, volume, vwap;
};

struct DayResult {
    Percentiles pct;
    std::vector<int> flags, quadrant, cls;
    Series bull_score, bear_score;
    std::vector<int> bull_order, bear_order;  // indices of scored stocks, best first
    double bull_cut_est = kNaN, bull_cut_dev = kNaN, bear_cut_est = kNaN, bear_cut_dev = kNaN;
};

using Weights = std::array<double, 5>;  // trend, consistency, relative strength, volume, VWAP position

// Percentile rank of each value among the non-NaN values: average rank of ties, scaled to 0..100.
// Sorting by merge sort makes this O(n log n).
Series percentile_ranks(const Series& x);

// Value at the given percentile (nearest-rank) of the non-NaN values, read from the sorted list.
double percentile_cutoff(const Series& x, double pct);

// Full pipeline for one day: percentiles, rule flags, quadrants, scores, classes and rankings.
DayResult classify_day(const DayInputs& in, const Weights& w, const Thresholds& th = {});

// Re-scores a day from stored percentiles and flags with new weights (classes and rankings change too).
DayResult rescore_day(const Percentiles& pct, const std::vector<int>& flags, const std::vector<int>& quadrant,
                      const Weights& w, const Thresholds& th = {});

}  // namespace daa
