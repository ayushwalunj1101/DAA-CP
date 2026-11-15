#include "daa/backtest.hpp"

#include <cmath>
#include <numeric>
#include <stdexcept>

#include "daa/sorting.hpp"

namespace daa {

std::vector<TradeExit> simulate_exits(const Series& open, const Series& high, const Series& low, const Series& close,
                                      const std::vector<int>& bullish, const std::vector<int>& entries,
                                      const Series& entry_atr, int hold, double stop_atr) {
    const std::size_t n = close.size();
    if (open.size() != n || high.size() != n || low.size() != n || bullish.size() != n)
        throw std::invalid_argument("bar series must have the same length");
    if (entry_atr.size() != entries.size()) throw std::invalid_argument("one ATR per entry");
    if (hold < 1) throw std::invalid_argument("hold must be at least 1");
    std::vector<TradeExit> out;
    out.reserve(entries.size());
    for (std::size_t k = 0; k < entries.size(); ++k) {
        const int e = entries[k];
        if (e < 0 || static_cast<std::size_t>(e) >= n) throw std::invalid_argument("entry index out of range");
        const double stop = open[static_cast<std::size_t>(e)] - stop_atr * entry_atr[k];
        TradeExit x{static_cast<int>(n) - 1, close[n - 1], EXIT_END};
        for (std::size_t t = static_cast<std::size_t>(e); t < n; ++t) {
            if (low[t] <= stop) {
                x = {static_cast<int>(t), std::fmin(open[t], stop), EXIT_STOP};
                if (t == static_cast<std::size_t>(e)) x.exit_price = stop;  // entry was at this open
                break;
            }
            if (static_cast<int>(t) - e + 1 >= hold) {
                x = {static_cast<int>(t), close[t], EXIT_TIME};
                break;
            }
            if (!bullish[t] && t + 1 < n) {
                x = {static_cast<int>(t) + 1, open[t + 1], EXIT_SIGNAL};
                break;
            }
        }
        out.push_back(x);
    }
    return out;
}

std::vector<int> interval_scheduling(const std::vector<int>& start, const std::vector<int>& end) {
    if (start.size() != end.size()) throw std::invalid_argument("start and end sizes differ");
    std::vector<int> idx(start.size());
    std::iota(idx.begin(), idx.end(), 0);
    merge_sort(idx, [&](int a, int b) { return end[static_cast<std::size_t>(a)] < end[static_cast<std::size_t>(b)]; });
    std::vector<int> chosen;
    long long last_end = -(1LL << 60);
    for (int i : idx) {
        if (start[static_cast<std::size_t>(i)] > last_end) {
            chosen.push_back(i);
            last_end = end[static_cast<std::size_t>(i)];
        }
    }
    merge_sort(chosen);
    return chosen;
}

HindsightPath hindsight_longest_path(const std::vector<Series>& closes, int max_hold, double cost_per_side) {
    if (max_hold < 1) throw std::invalid_argument("max_hold must be at least 1");
    const std::size_t D = closes.size();
    HindsightPath r;
    if (D == 0) return r;
    const std::size_t S = closes[0].size();
    for (const auto& row : closes)
        if (row.size() != S) throw std::invalid_argument("every day needs the same number of stocks");
    // Log closes once, so every edge weight is a subtraction: ln(b / a) = ln b - ln a.
    std::vector<Series> lg(D, Series(S, kNaN));
    for (std::size_t d = 0; d < D; ++d)
        for (std::size_t s = 0; s < S; ++s)
            if (closes[d][s] > 0) lg[d][s] = std::log(closes[d][s]);
    // best[j] = longest path from day 0 to day j; prev[j] / via[j] record the last edge used.
    std::vector<double> best(D, 0.0);
    std::vector<int> prev(D, -1), via(D, -1);
    const double cost = 2 * cost_per_side;
    for (std::size_t j = 1; j < D; ++j) {
        best[j] = best[j - 1];  // cash edge (j-1 -> j)
        prev[j] = static_cast<int>(j) - 1;
        via[j] = -1;
        const std::size_t first = j > static_cast<std::size_t>(max_hold) ? j - static_cast<std::size_t>(max_hold) : 0;
        for (std::size_t i = first; i < j; ++i) {
            double edge = -INFINITY;
            int pick = -1;
            const Series &li = lg[i], &lj = lg[j];
            for (std::size_t s = 0; s < S; ++s) {
                const double g = lj[s] - li[s];  // NaN when either day is not tradable; NaN > edge is false
                if (g > edge) {
                    edge = g;
                    pick = static_cast<int>(s);
                }
            }
            if (pick >= 0 && best[i] + edge - cost > best[j]) {
                best[j] = best[i] + edge - cost;
                prev[j] = static_cast<int>(i);
                via[j] = pick;
            }
        }
    }
    r.total_log_return = best[D - 1];
    for (int j = static_cast<int>(D) - 1; j > 0; j = prev[static_cast<std::size_t>(j)]) {
        if (via[static_cast<std::size_t>(j)] >= 0) {
            r.buy_day.insert(r.buy_day.begin(), prev[static_cast<std::size_t>(j)]);
            r.sell_day.insert(r.sell_day.begin(), j);
            r.stock.insert(r.stock.begin(), via[static_cast<std::size_t>(j)]);
        }
    }
    return r;
}

}  // namespace daa
