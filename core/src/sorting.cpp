#include "daa/sorting.hpp"

#include <algorithm>
#include <stdexcept>

namespace daa {

namespace {
long long inv_rec(std::vector<double>& a, std::vector<double>& buf, std::size_t lo, std::size_t hi, OpCounter* ops) {
    if (hi - lo < 2) return 0;
    std::size_t mid = lo + (hi - lo) / 2;
    long long count = inv_rec(a, buf, lo, mid, ops) + inv_rec(a, buf, mid, hi, ops);
    std::size_t i = lo, j = mid, k = lo;
    while (i < mid && j < hi) {
        if (ops) ops->add();
        if (a[j] < a[i]) {
            count += static_cast<long long>(mid - i);  // a[j] is smaller than every remaining left element
            buf[k++] = a[j++];
        } else {
            buf[k++] = a[i++];
        }
    }
    while (i < mid) buf[k++] = a[i++];
    while (j < hi) buf[k++] = a[j++];
    for (std::size_t t = lo; t < hi; ++t) a[t] = buf[t];
    return count;
}
}  // namespace

long long count_inversions(std::vector<double> a, OpCounter* ops) {
    std::vector<double> buf(a.size());
    return inv_rec(a, buf, 0, a.size(), ops);
}

long long count_inversions_naive(const std::vector<double>& a, OpCounter* ops) {
    long long count = 0;
    for (std::size_t i = 0; i < a.size(); ++i)
        for (std::size_t j = i + 1; j < a.size(); ++j) {
            if (ops) ops->add();
            if (a[j] < a[i]) ++count;
        }
    return count;
}

long long count_tie_pairs(std::vector<double> a, std::vector<long long>* group_sizes) {
    merge_sort(a);
    long long pairs = 0;
    std::size_t i = 0;
    while (i < a.size()) {
        std::size_t j = i;
        while (j < a.size() && a[j] == a[i]) ++j;
        long long g = static_cast<long long>(j - i);
        if (g > 1) {
            pairs += g * (g - 1) / 2;
            if (group_sizes) group_sizes->push_back(g);
        }
        i = j;
    }
    return pairs;
}

long long ranking_distance(const std::vector<int>& before, const std::vector<int>& after) {
    if (before.size() != after.size()) throw std::invalid_argument("rankings must have the same items");
    // Position of each item in `before`; then count inversions of those positions in `after` order.
    int max_id = -1;
    for (int id : before) max_id = std::max(max_id, id);
    std::vector<long long> pos(static_cast<std::size_t>(max_id + 1), -1);
    for (std::size_t i = 0; i < before.size(); ++i) pos[static_cast<std::size_t>(before[i])] = static_cast<long long>(i);
    std::vector<double> seq;
    seq.reserve(after.size());
    for (int id : after) {
        if (id < 0 || id > max_id || pos[static_cast<std::size_t>(id)] < 0)
            throw std::invalid_argument("rankings must have the same items");
        seq.push_back(static_cast<double>(pos[static_cast<std::size_t>(id)]));
    }
    return count_inversions(seq);
}

}  // namespace daa
