#pragma once
// Technical indicators in O(n) per stock using sliding windows and prefix sums.
// Convention: values that need more history than is available are NaN.
#include "daa/common.hpp"

namespace daa {

// P[0] = 0, P[i + 1] = P[i] + x[i]; any window sum is then P[j] - P[i] in O(1).
Series prefix_sums(const Series& x);

// Exponential moving average, seeded with the simple average of the first n values.
Series ema(const Series& x, int n);

// Wilder's RSI over n changes (first value at index n).
Series rsi_wilder(const Series& close, int n);

// True range: max(high - low, |high - prev close|, |low - prev close|); day 0 uses high - low.
Series true_range(const Series& high, const Series& low, const Series& close);

// Wilder's average true range, seeded with the simple average of the first n true ranges.
Series atr_wilder(const Series& tr, int n);

// Mean of the previous n values x[t-n .. t-1] (excludes today), via prefix sums.
Series rolling_mean_prev(const Series& x, int n);

// Relative volume: today's volume / average volume of the previous n days.
Series relative_volume(const Series& volume, int n);

// Volume-weighted average of `price` over the last n days (t-n+1 .. t), via prefix sums.
Series rolling_vwap(const Series& price, const Series& volume, int n);

// Highest / lowest value over the previous n days (excludes today): monotonic deque, O(n) total.
Series rolling_max_prev(const Series& x, int n);
Series rolling_min_prev(const Series& x, int n);

// ln(x[t] / x[t-n]).
Series log_change(const Series& x, int n);

// x[t] / x[t-n] - 1, in percent.
Series pct_change(const Series& x, int n);

// Mean of the last n values x[t-n+1 .. t] (includes today), via prefix sums.
Series rolling_mean(const Series& x, int n);

// 1 when x[t] > median + k * MAD of the previous n values, else 0 (median found by merge sort).
Series spike_flags(const Series& x, int n, double k);

// Over the last n days: (average RVOL on up days + 0.01) / (average RVOL on down days + 0.01).
Series up_down_volume_ratio(const Series& close, const Series& rvol, int n);

}  // namespace daa
