#pragma once
// Algorithm Lab: times one algorithm on a generated input of size n and counts its basic operations.
#include <cstdint>
#include <string>
#include <vector>

namespace daa {

struct BenchResult {
    double millis = 0;       // best of `repeats` runs
    std::uint64_t ops = 0;   // comparisons / relaxations / DP cells / nodes, when the algorithm counts them
};

// Names accepted by run_benchmark.
std::vector<std::string> benchmark_names();

// input: "random", "sorted" or "nearly_sorted" (1% of positions swapped). Throws on unknown names.
BenchResult run_benchmark(const std::string& name, long long n, const std::string& input, std::uint64_t seed,
                          int repeats);

}  // namespace daa
