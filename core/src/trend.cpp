#include "daa/trend.hpp"

#include <cmath>
#include <stdexcept>

#include "daa/search.hpp"
#include "daa/sorting.hpp"

namespace daa {

MannKendall mann_kendall(const std::vector<double>& x) {
    MannKendall r;
    const long long n = static_cast<long long>(x.size());
    if (n < 2) return r;
    const long long pairs = n * (n - 1) / 2;
    std::vector<long long> groups;
    r.discordant = count_inversions(x);
    r.ties = count_tie_pairs(x, &groups);
    r.concordant = pairs - r.discordant - r.ties;
    r.s = static_cast<double>(r.concordant - r.discordant);
    double var = static_cast<double>(n) * (n - 1) * (2 * n + 5);
    for (long long t : groups) var -= static_cast<double>(t) * (t - 1) * (2 * t + 5);
    r.var = var / 18.0;
    if (r.var > 0) {
        if (r.s > 0)
            r.z = (r.s - 1.0) / std::sqrt(r.var);
        else if (r.s < 0)
            r.z = (r.s + 1.0) / std::sqrt(r.var);
    }
    return r;
}

std::size_t lis_length(const std::vector<double>& x, OpCounter* ops) {
    std::vector<double> tails;
    for (double v : x) {
        // First tail >= v: replacing it keeps tails strictly increasing and as small as possible.
        std::size_t lo = 0, hi = tails.size();
        while (lo < hi) {
            std::size_t mid = lo + (hi - lo) / 2;
            if (ops) ops->add();
            if (tails[mid] < v)
                lo = mid + 1;
            else
                hi = mid;
        }
        if (lo == tails.size())
            tails.push_back(v);
        else
            tails[lo] = v;
    }
    return tails.size();
}

std::size_t lds_length(const std::vector<double>& x) {
    std::vector<double> neg(x.size());
    for (std::size_t i = 0; i < x.size(); ++i) neg[i] = -x[i];
    return lis_length(neg);
}

std::size_t lis_length_dp(const std::vector<double>& x, OpCounter* ops) {
    std::vector<std::size_t> best(x.size(), 1);
    std::size_t answer = x.empty() ? 0 : 1;
    for (std::size_t i = 0; i < x.size(); ++i) {
        for (std::size_t j = 0; j < i; ++j) {
            if (ops) ops->add();
            if (x[j] < x[i] && best[j] + 1 > best[i]) best[i] = best[j] + 1;
        }
        if (best[i] > answer) answer = best[i];
    }
    return answer;
}

std::vector<std::vector<unsigned long long>> binomial_table(int max_n) {
    if (max_n < 0 || max_n > 62) throw std::invalid_argument("binomial_table supports 0 <= n <= 62");
    std::vector<std::vector<unsigned long long>> c(static_cast<std::size_t>(max_n) + 1);
    for (int n = 0; n <= max_n; ++n) {
        c[static_cast<std::size_t>(n)].assign(static_cast<std::size_t>(n) + 1, 1ULL);
        for (int k = 1; k < n; ++k)
            c[static_cast<std::size_t>(n)][static_cast<std::size_t>(k)] =
                c[static_cast<std::size_t>(n) - 1][static_cast<std::size_t>(k) - 1] +
                c[static_cast<std::size_t>(n) - 1][static_cast<std::size_t>(k)];
    }
    return c;
}

double sign_test_p(int k, int n) {
    if (n <= 0) return 1.0;
    if (k <= 0) return 1.0;
    if (k > n) return 0.0;
    if (n <= 62) {
        static const auto table = binomial_table(62);
        unsigned long long tail = 0;
        for (int i = k; i <= n; ++i) tail += table[static_cast<std::size_t>(n)][static_cast<std::size_t>(i)];
        return static_cast<double>(static_cast<long double>(tail) / std::ldexp(1.0L, n));
    }
    // Larger n: sum terms in log space (not needed for 20/60-day windows, kept for safety).
    long double tail = 0;
    for (int i = k; i <= n; ++i)
        tail += std::exp(std::lgamma(n + 1.0L) - std::lgamma(i + 1.0L) - std::lgamma(n - i + 1.0L) - n * std::log(2.0L));
    return static_cast<double>(tail);
}

RollingTrend rolling_trend(const Series& close, int window) {
    if (window < 2) throw std::invalid_argument("window must be at least 2");
    const std::size_t n = close.size(), w = static_cast<std::size_t>(window);
    RollingTrend r;
    for (Series* s : {&r.mk_s, &r.mk_z, &r.lis_ratio, &r.lds_ratio, &r.up_days, &r.down_days, &r.sign_p_up,
                      &r.sign_p_down})
        s->assign(n, kNaN);
    std::vector<double> win;
    win.reserve(w);
    for (std::size_t t = w; t < n; ++t) {
        win.assign(close.begin() + static_cast<std::ptrdiff_t>(t - w + 1), close.begin() + static_cast<std::ptrdiff_t>(t + 1));
        MannKendall mk = mann_kendall(win);
        r.mk_s[t] = mk.s;
        r.mk_z[t] = mk.z;
        r.lis_ratio[t] = static_cast<double>(lis_length(win)) / static_cast<double>(w);
        r.lds_ratio[t] = static_cast<double>(lds_length(win)) / static_cast<double>(w);
        int up = 0, down = 0;
        for (std::size_t s = t - w + 1; s <= t; ++s) {
            if (close[s] > close[s - 1])
                ++up;
            else if (close[s] < close[s - 1])
                ++down;
        }
        r.up_days[t] = up;
        r.down_days[t] = down;
        r.sign_p_up[t] = sign_test_p(up, up + down);
        r.sign_p_down[t] = sign_test_p(down, up + down);
    }
    return r;
}

}  // namespace daa
