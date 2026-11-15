#pragma once
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

namespace daa {

using Series = std::vector<double>;

inline constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();

inline bool is_nan(double v) { return std::isnan(v); }

// Counts elementary operations (comparisons, nodes explored) for the Algorithm Lab.
struct OpCounter {
    std::uint64_t count = 0;
    void add(std::uint64_t k = 1) { count += k; }
};

}  // namespace daa
