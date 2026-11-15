#include "daa/search.hpp"

namespace daa {

std::pair<std::size_t, std::size_t> date_range(const std::vector<std::string>& dates, const std::string& from,
                                               const std::string& to) {
    std::size_t first = lower_bound_idx(dates, from);
    std::size_t last = upper_bound_idx(dates, to);
    if (last < first) last = first;
    return {first, last};
}

long long last_at_or_before(const std::vector<std::string>& dates, const std::string& x) {
    return static_cast<long long>(upper_bound_idx(dates, x)) - 1;
}

std::pair<std::size_t, std::size_t> prefix_range(const std::vector<std::string>& sorted, const std::string& prefix) {
    if (prefix.empty()) return {0, sorted.size()};
    std::size_t first = lower_bound_idx(sorted, prefix);
    // Strings with the prefix are contiguous; they end before the smallest string greater than every
    // string with the prefix, which is the prefix with its last byte incremented.
    std::string succ = prefix;
    while (!succ.empty() && static_cast<unsigned char>(succ.back()) == 0xFF) succ.pop_back();
    if (succ.empty()) return {first, sorted.size()};
    succ.back() = static_cast<char>(static_cast<unsigned char>(succ.back()) + 1);
    std::size_t last = lower_bound_idx(sorted, succ);
    return {first, last};
}

}  // namespace daa
