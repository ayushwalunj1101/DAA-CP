#include "daa/classify.hpp"

#include <cmath>
#include <numeric>
#include <stdexcept>

#include "daa/sorting.hpp"

namespace daa {

Series percentile_ranks(const Series& x) {
    Series out(x.size(), kNaN);
    std::vector<int> idx;
    for (std::size_t i = 0; i < x.size(); ++i)
        if (!is_nan(x[i])) idx.push_back(static_cast<int>(i));
    const std::size_t m = idx.size();
    if (m == 0) return out;
    merge_sort(idx, [&](int a, int b) { return x[static_cast<std::size_t>(a)] < x[static_cast<std::size_t>(b)]; });
    std::size_t i = 0;
    while (i < m) {
        std::size_t j = i;
        while (j < m && x[static_cast<std::size_t>(idx[j])] == x[static_cast<std::size_t>(idx[i])]) ++j;
        double avg_pos = (static_cast<double>(i) + static_cast<double>(j - 1)) / 2.0;  // ties share the average
        double pct = m == 1 ? 50.0 : 100.0 * avg_pos / static_cast<double>(m - 1);
        for (std::size_t t = i; t < j; ++t) out[static_cast<std::size_t>(idx[t])] = pct;
        i = j;
    }
    return out;
}

double percentile_cutoff(const Series& x, double pct) {
    std::vector<double> v;
    for (double e : x)
        if (!is_nan(e)) v.push_back(e);
    if (v.empty()) return kNaN;
    merge_sort(v);
    double rank = std::ceil(pct / 100.0 * static_cast<double>(v.size()));
    std::size_t k = rank < 1 ? 0 : static_cast<std::size_t>(rank) - 1;
    if (k >= v.size()) k = v.size() - 1;
    return v[k];
}

namespace {

void check_sizes(const DayInputs& in) {
    const std::size_t n = in.close.size();
    for (const Series* s : {&in.ema50, &in.ema200, &in.high20, &in.low20, &in.mk_z20, &in.mk_z60, &in.lis60,
                            &in.lds60, &in.sign_p_up60, &in.sign_p_down60, &in.rs60, &in.updown_vol20, &in.vwap_dist,
                            &in.ret5, &in.rvol5_avg})
        if (s->size() != n) throw std::invalid_argument("all day inputs must have the same length");
}

// Indices with a valid score, ordered best first: sort by the tie-break key, then (stably) by score.
std::vector<int> ranking(const Series& score, const Series& tiebreak) {
    std::vector<int> idx;
    for (std::size_t i = 0; i < score.size(); ++i)
        if (!is_nan(score[i])) idx.push_back(static_cast<int>(i));
    auto key = [](const Series& s, int i) {
        double v = s[static_cast<std::size_t>(i)];
        return is_nan(v) ? -1e300 : v;
    };
    merge_sort(idx, [&](int a, int b) { return key(tiebreak, a) > key(tiebreak, b); });
    merge_sort(idx, [&](int a, int b) { return key(score, a) > key(score, b); });
    return idx;
}

void score_and_classify(DayResult& r, const Weights& w, const Thresholds& th) {
    const std::size_t n = r.flags.size();
    const double wsum = w[0] + w[1] + w[2] + w[3] + w[4];
    if (!(wsum > 0)) throw std::invalid_argument("weights must sum to a positive number");
    r.bull_score.assign(n, kNaN);
    r.bear_score.assign(n, kNaN);
    const Percentiles& p = r.pct;
    for (std::size_t i = 0; i < n; ++i) {
        const double bull[5] = {p.trend[i], p.cons_bull[i], p.rs[i], p.volume[i], p.vwap[i]};
        const double bear[5] = {100 - p.trend[i], p.cons_bear[i], 100 - p.rs[i], 100 - p.volume[i], 100 - p.vwap[i]};
        bool ok = true;
        double sb = 0, sr = 0;
        for (int k = 0; k < 5; ++k) {
            if (is_nan(bull[k]) || is_nan(bear[k])) ok = false;
            sb += w[static_cast<std::size_t>(k)] * bull[k];
            sr += w[static_cast<std::size_t>(k)] * bear[k];
        }
        if (ok) {
            r.bull_score[i] = sb / wsum;
            r.bear_score[i] = sr / wsum;
        }
    }
    r.bull_cut_est = percentile_cutoff(r.bull_score, th.est_pct);
    r.bull_cut_dev = percentile_cutoff(r.bull_score, th.dev_pct);
    r.bear_cut_est = percentile_cutoff(r.bear_score, th.est_pct);
    r.bear_cut_dev = percentile_cutoff(r.bear_score, th.dev_pct);

    r.cls.assign(n, NEUTRAL);
    for (std::size_t i = 0; i < n; ++i) {
        if (is_nan(r.bull_score[i])) continue;
        const int f = r.flags[i];
        int bull = NEUTRAL, bear = NEUTRAL;
        if ((f & EST_BULL_RULES) && r.bull_score[i] >= r.bull_cut_est)
            bull = EST_BULL;
        else if ((f & DEV_BULL_RULES) && r.bull_score[i] >= r.bull_cut_dev)
            bull = DEV_BULL;
        if ((f & EST_BEAR_RULES) && r.bear_score[i] >= r.bear_cut_est)
            bear = EST_BEAR;
        else if ((f & DEV_BEAR_RULES) && r.bear_score[i] >= r.bear_cut_dev)
            bear = DEV_BEAR;
        r.cls[i] = (bull != NEUTRAL && bear != NEUTRAL) ? NEUTRAL : (bull != NEUTRAL ? bull : bear);  // conflicting
    }
    r.bull_order = ranking(r.bull_score, p.rs);
    Series inv_rs(n);
    for (std::size_t i = 0; i < n; ++i) inv_rs[i] = is_nan(p.rs[i]) ? kNaN : 100 - p.rs[i];
    r.bear_order = ranking(r.bear_score, inv_rs);
}

}  // namespace

DayResult classify_day(const DayInputs& in, const Weights& w, const Thresholds& th) {
    check_sizes(in);
    const std::size_t n = in.close.size();
    DayResult r;
    r.pct.trend = percentile_ranks(in.mk_z60);
    r.pct.cons_bull = percentile_ranks(in.lis60);
    r.pct.cons_bear = percentile_ranks(in.lds60);
    r.pct.rs = percentile_ranks(in.rs60);
    r.pct.volume = percentile_ranks(in.updown_vol20);
    r.pct.vwap = percentile_ranks(in.vwap_dist);
    r.flags.assign(n, 0);
    r.quadrant.assign(n, Q_NONE);
    for (std::size_t i = 0; i < n; ++i) {
        const double c = in.close[i], e50 = in.ema50[i], e200 = in.ema200[i];
        if (!is_nan(in.ret5[i]) && !is_nan(in.rvol5_avg[i])) {
            const bool up = in.ret5[i] >= 0, heavy = in.rvol5_avg[i] > 1.0;
            r.quadrant[i] = up ? (heavy ? ACCUMULATION : WEAK_RALLY) : (heavy ? DISTRIBUTION : WEAK_SELLOFF);
        }
        int f = 0;
        if (in.mk_z60[i] >= th.z && c > e50 && e50 > e200 && in.sign_p_up60[i] < th.p) f |= EST_BULL_RULES;
        if (in.mk_z20[i] >= th.z || (c > in.high20[i] && r.quadrant[i] == ACCUMULATION)) f |= DEV_BULL_RULES;
        if (in.mk_z60[i] <= -th.z && c < e50 && e50 < e200 && in.sign_p_down60[i] < th.p) f |= EST_BEAR_RULES;
        if (in.mk_z20[i] <= -th.z || (c < in.low20[i] && r.quadrant[i] == DISTRIBUTION)) f |= DEV_BEAR_RULES;
        r.flags[i] = f;  // comparisons with NaN are false, so missing inputs never set a flag
    }
    score_and_classify(r, w, th);
    return r;
}

DayResult rescore_day(const Percentiles& pct, const std::vector<int>& flags, const std::vector<int>& quadrant,
                      const Weights& w, const Thresholds& th) {
    DayResult r;
    r.pct = pct;
    r.flags = flags;
    r.quadrant = quadrant;
    score_and_classify(r, w, th);
    return r;
}

}  // namespace daa
