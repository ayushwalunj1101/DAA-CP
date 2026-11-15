#pragma once
// Unit I: binary search.
#include <cstddef>
#include <string>
#include <utility>
#include <vector>

namespace daa {

// First index i with !(a[i] < x), i.e. a[i] >= x; a.size() if none. O(log n).
// Loop invariant: every index < lo holds a value < x, every index >= hi holds a value >= x.
template <class T, class Less>
std::size_t lower_bound_idx(const std::vector<T>& a, const T& x, Less less) {
    std::size_t lo = 0, hi = a.size();
    while (lo < hi) {
        std::size_t mid = lo + (hi - lo) / 2;
        if (less(a[mid], x))
            lo = mid + 1;
        else
            hi = mid;
    }
    return lo;
}

template <class T>
std::size_t lower_bound_idx(const std::vector<T>& a, const T& x) {
    return lower_bound_idx(a, x, [](const T& p, const T& q) { return p < q; });
}

// First index i with a[i] > x; a.size() if none. O(log n).
template <class T>
std::size_t upper_bound_idx(const std::vector<T>& a, const T& x) {
    std::size_t lo = 0, hi = a.size();
    while (lo < hi) {
        std::size_t mid = lo + (hi - lo) / 2;
        if (!(x < a[mid]))
            lo = mid + 1;
        else
            hi = mid;
    }
    return lo;
}

// Half-open index range [first, last) of the sorted ISO dates that lie within [from, to].
std::pair<std::size_t, std::size_t> date_range(const std::vector<std::string>& dates, const std::string& from,
                                               const std::string& to);

// Index of the last date <= x, or -1 when every date is after x.
long long last_at_or_before(const std::vector<std::string>& dates, const std::string& x);

// Index range [first, last) of the sorted strings that start with prefix (for Ctrl+K search).
std::pair<std::size_t, std::size_t> prefix_range(const std::vector<std::string>& sorted, const std::string& prefix);

}  // namespace daa
