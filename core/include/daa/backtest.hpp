#pragma once
// Backtest helpers: trade exits, interval scheduling (Unit IV greedy) and the hindsight-optimal
// trade sequence as a longest path in a DAG of trading days (Unit III).
#include <vector>

#include "daa/common.hpp"

namespace daa {

enum ExitReason : int { EXIT_STOP = 0, EXIT_TIME = 1, EXIT_SIGNAL = 2, EXIT_END = 3 };

struct TradeExit {
    int exit_index;    // bar index of the exit
    double exit_price;
    int reason;
};

// For each entry bar (entry at that bar's open), the exit under these rules, first match wins:
//  - stop: a bar's low touches entry - stop_atr * atr (exit at the stop, or at the open after a gap below it);
//  - time: the trade has been held `hold` bars (exit at that bar's close);
//  - signal: the stock is no longer bullish at a bar's close (exit at the next bar's open);
//  - end of data: exit at the last close.
std::vector<TradeExit> simulate_exits(const Series& open, const Series& high, const Series& low, const Series& close,
                                      const std::vector<int>& bullish, const std::vector<int>& entries,
                                      const Series& entry_atr, int hold, double stop_atr);

// Interval scheduling: the largest set of pairwise disjoint closed intervals [start, end]
// (next start > previous end), by the earliest-finish-time greedy rule. Returns chosen indices.
// Exchange argument: some optimal schedule starts with the interval that ends first.
std::vector<int> interval_scheduling(const std::vector<int>& start, const std::vector<int>& end);

struct HindsightPath {
    double total_log_return = 0;
    std::vector<int> buy_day, sell_day, stock;  // the trades on the longest path
};

// Days 0..D-1 are DAG nodes in time order (already a topological order). Edge d -> d+1 (weight 0) stays
// in cash; edge i -> j (0 < j - i <= max_hold) buys the best stock at close i and sells at close j,
// weight max_s ln(c[j][s] / c[i][s]) - 2 cost. closes is D x S (NaN = not tradable); O(D * max_hold * S).
HindsightPath hindsight_longest_path(const std::vector<Series>& closes, int max_hold, double cost_per_side);

}  // namespace daa
