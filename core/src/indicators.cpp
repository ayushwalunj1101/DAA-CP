#include "daa/indicators.hpp"

#include <cmath>
#include <deque>
#include <stdexcept>

#include "daa/sorting.hpp"

namespace daa {

namespace {
void check_window(int n) {
    if (n < 1) throw std::invalid_argument("window must be positive");
}
std::size_t W(int n) { return static_cast<std::size_t>(n); }
}  // namespace

Series prefix_sums(const Series& x) {
    Series p(x.size() + 1, 0.0);
    for (std::size_t i = 0; i < x.size(); ++i) p[i + 1] = p[i] + x[i];
    return p;
}

Series ema(const Series& x, int n) {
    check_window(n);
    Series out(x.size(), kNaN);
    if (x.size() < W(n)) return out;
    double alpha = 2.0 / (n + 1.0), sum = 0.0;
    for (std::size_t i = 0; i < W(n); ++i) sum += x[i];
    out[W(n) - 1] = sum / n;
    for (std::size_t i = W(n); i < x.size(); ++i) out[i] = alpha * x[i] + (1.0 - alpha) * out[i - 1];
    return out;
}

Series rsi_wilder(const Series& close, int n) {
    check_window(n);
    Series out(close.size(), kNaN);
    if (close.size() <= W(n)) return out;
    double gain = 0.0, loss = 0.0;
    for (std::size_t i = 1; i <= W(n); ++i) {
        double d = close[i] - close[i - 1];
        (d > 0 ? gain : loss) += std::fabs(d);
    }
    gain /= n;
    loss /= n;
    auto rsi = [](double g, double l) { return l == 0.0 ? (g == 0.0 ? 50.0 : 100.0) : 100.0 - 100.0 / (1.0 + g / l); };
    out[W(n)] = rsi(gain, loss);
    for (std::size_t i = W(n) + 1; i < close.size(); ++i) {
        double d = close[i] - close[i - 1];
        gain = (gain * (n - 1) + (d > 0 ? d : 0.0)) / n;
        loss = (loss * (n - 1) + (d < 0 ? -d : 0.0)) / n;
        out[i] = rsi(gain, loss);
    }
    return out;
}

Series true_range(const Series& high, const Series& low, const Series& close) {
    Series tr(close.size(), kNaN);
    for (std::size_t i = 0; i < close.size(); ++i) {
        double hl = high[i] - low[i];
        if (i == 0) {
            tr[i] = hl;
        } else {
            tr[i] = std::fmax(hl, std::fmax(std::fabs(high[i] - close[i - 1]), std::fabs(low[i] - close[i - 1])));
        }
    }
    return tr;
}

Series atr_wilder(const Series& tr, int n) {
    check_window(n);
    Series out(tr.size(), kNaN);
    if (tr.size() < W(n)) return out;
    double sum = 0.0;
    for (std::size_t i = 0; i < W(n); ++i) sum += tr[i];
    out[W(n) - 1] = sum / n;
    for (std::size_t i = W(n); i < tr.size(); ++i) out[i] = (out[i - 1] * (n - 1) + tr[i]) / n;
    return out;
}

Series rolling_mean_prev(const Series& x, int n) {
    check_window(n);
    Series p = prefix_sums(x), out(x.size(), kNaN);
    for (std::size_t t = W(n); t < x.size(); ++t) out[t] = (p[t] - p[t - W(n)]) / n;
    return out;
}

Series relative_volume(const Series& volume, int n) {
    Series avg = rolling_mean_prev(volume, n), out(volume.size(), kNaN);
    for (std::size_t t = 0; t < volume.size(); ++t)
        if (!is_nan(avg[t]) && avg[t] > 0) out[t] = volume[t] / avg[t];
    return out;
}

Series rolling_vwap(const Series& price, const Series& volume, int n) {
    check_window(n);
    Series pv(price.size());
    for (std::size_t i = 0; i < price.size(); ++i) pv[i] = price[i] * volume[i];
    Series ppv = prefix_sums(pv), pvol = prefix_sums(volume), out(price.size(), kNaN);
    for (std::size_t t = W(n) - 1; t < price.size(); ++t) {
        double vol = pvol[t + 1] - pvol[t + 1 - W(n)];
        if (vol > 0) out[t] = (ppv[t + 1] - ppv[t + 1 - W(n)]) / vol;
    }
    return out;
}

namespace {
// Sliding-window extreme over x[t-n .. t-1]. The deque holds indices whose values are monotonic,
// so the front is the window's extreme; each index is pushed and popped at most once: O(len).
template <class Better>
Series rolling_extreme_prev(const Series& x, int n, Better better) {
    check_window(n);
    Series out(x.size(), kNaN);
    std::deque<std::size_t> dq;
    for (std::size_t t = 0; t < x.size(); ++t) {
        if (t >= W(n)) {
            while (!dq.empty() && dq.front() < t - W(n)) dq.pop_front();
            out[t] = x[dq.front()];
        }
        while (!dq.empty() && !better(x[dq.back()], x[t])) dq.pop_back();
        dq.push_back(t);
    }
    return out;
}
}  // namespace

Series rolling_max_prev(const Series& x, int n) {
    return rolling_extreme_prev(x, n, [](double kept, double incoming) { return kept > incoming; });
}

Series rolling_min_prev(const Series& x, int n) {
    return rolling_extreme_prev(x, n, [](double kept, double incoming) { return kept < incoming; });
}

Series log_change(const Series& x, int n) {
    check_window(n);
    Series out(x.size(), kNaN);
    for (std::size_t t = W(n); t < x.size(); ++t)
        if (x[t] > 0 && x[t - W(n)] > 0) out[t] = std::log(x[t] / x[t - W(n)]);
    return out;
}

Series pct_change(const Series& x, int n) {
    check_window(n);
    Series out(x.size(), kNaN);
    for (std::size_t t = W(n); t < x.size(); ++t)
        if (x[t - W(n)] != 0) out[t] = (x[t] / x[t - W(n)] - 1.0) * 100.0;
    return out;
}

Series rolling_mean(const Series& x, int n) {
    check_window(n);
    Series out(x.size(), kNaN);
    // Prefix sums that skip NaN, with a count of valid values, so warm-up NaNs do not poison later windows.
    Series p(x.size() + 1, 0.0), c(x.size() + 1, 0.0);
    for (std::size_t i = 0; i < x.size(); ++i) {
        bool ok = !is_nan(x[i]);
        p[i + 1] = p[i] + (ok ? x[i] : 0.0);
        c[i + 1] = c[i] + (ok ? 1.0 : 0.0);
    }
    for (std::size_t t = W(n) - 1; t < x.size(); ++t) {
        double cnt = c[t + 1] - c[t + 1 - W(n)];
        if (cnt == n) out[t] = (p[t + 1] - p[t + 1 - W(n)]) / n;
    }
    return out;
}

namespace {
double median_sorted(const std::vector<double>& s) {
    std::size_t m = s.size() / 2;
    return s.size() % 2 ? s[m] : 0.5 * (s[m - 1] + s[m]);
}
}  // namespace

Series spike_flags(const Series& x, int n, double k) {
    check_window(n);
    Series out(x.size(), kNaN);
    std::vector<double> win, dev;
    for (std::size_t t = W(n); t < x.size(); ++t) {
        win.assign(x.begin() + static_cast<std::ptrdiff_t>(t - W(n)), x.begin() + static_cast<std::ptrdiff_t>(t));
        merge_sort(win);
        double med = median_sorted(win);
        dev.resize(win.size());
        for (std::size_t i = 0; i < win.size(); ++i) dev[i] = std::fabs(win[i] - med);
        merge_sort(dev);
        double mad = median_sorted(dev);
        out[t] = x[t] > med + k * mad ? 1.0 : 0.0;
    }
    return out;
}

Series up_down_volume_ratio(const Series& close, const Series& rvol, int n) {
    check_window(n);
    Series out(close.size(), kNaN);
    for (std::size_t t = W(n); t < close.size(); ++t) {
        double up = 0, down = 0;
        int nu = 0, nd = 0;
        bool ok = true;
        for (std::size_t s = t - W(n) + 1; s <= t; ++s) {
            if (is_nan(rvol[s])) {
                ok = false;
                break;
            }
            if (close[s] > close[s - 1]) {
                up += rvol[s];
                ++nu;
            } else if (close[s] < close[s - 1]) {
                down += rvol[s];
                ++nd;
            }
        }
        if (!ok) continue;
        double au = nu ? up / nu : 0.0, ad = nd ? down / nd : 0.0;
        out[t] = (au + 0.01) / (ad + 0.01);
    }
    return out;
}

}  // namespace daa
