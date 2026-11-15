#pragma once
// Unit II: merge sort, counting inversions, quicksort (fixed and randomized pivot).
#include <cstddef>
#include <cstdint>
#include <random>
#include <utility>
#include <vector>

#include "daa/common.hpp"

namespace daa {

namespace detail {
template <class T, class Less>
void merge_sort_rec(std::vector<T>& a, std::vector<T>& buf, std::size_t lo, std::size_t hi, Less& less,
                    OpCounter* ops) {
    if (hi - lo < 2) return;
    std::size_t mid = lo + (hi - lo) / 2;
    merge_sort_rec(a, buf, lo, mid, less, ops);
    merge_sort_rec(a, buf, mid, hi, less, ops);
    // Merge: take from the left run unless the right element is strictly smaller (keeps it stable).
    std::size_t i = lo, j = mid, k = lo;
    while (i < mid && j < hi) {
        if (ops) ops->add();
        if (less(a[j], a[i]))
            buf[k++] = std::move(a[j++]);
        else
            buf[k++] = std::move(a[i++]);
    }
    while (i < mid) buf[k++] = std::move(a[i++]);
    while (j < hi) buf[k++] = std::move(a[j++]);
    for (std::size_t t = lo; t < hi; ++t) a[t] = std::move(buf[t]);
}
}  // namespace detail

// Stable merge sort. T(n) = 2T(n/2) + Theta(n) = Theta(n log n) by the Master theorem (case 2); O(n) extra space.
template <class T, class Less>
void merge_sort(std::vector<T>& a, Less less, OpCounter* ops = nullptr) {
    std::vector<T> buf(a.size());
    detail::merge_sort_rec(a, buf, 0, a.size(), less, ops);
}

template <class T>
void merge_sort(std::vector<T>& a, OpCounter* ops = nullptr) {
    merge_sort(a, [](const T& p, const T& q) { return p < q; }, ops);
}

// Number of pairs i < j with a[j] < a[i] (equal values are not inversions), in O(n log n).
// Same recursion as merge sort: when an element of the right run is taken before the remaining
// left-run elements, it forms an inversion with each of them.
long long count_inversions(std::vector<double> a, OpCounter* ops = nullptr);

// O(n^2) reference count, used in tests and the Algorithm Lab.
long long count_inversions_naive(const std::vector<double>& a, OpCounter* ops = nullptr);

// Number of pairs i < j with a[i] == a[j], and the sizes of groups of equal values.
long long count_tie_pairs(std::vector<double> a, std::vector<long long>* group_sizes = nullptr);

// Kendall tau distance between two rankings of the same items: the number of pairs ordered
// differently. Both inputs list item ids from best to worst.
long long ranking_distance(const std::vector<int>& before, const std::vector<int>& after);

// ---------------------------------------------------------------- quicksort
enum class Pivot { Last, Random };

namespace detail {
// Lomuto partition around a[hi]; returns the pivot's final index.
template <class T, class Less>
std::size_t partition(std::vector<T>& a, std::size_t lo, std::size_t hi, Less& less, OpCounter* ops) {
    std::size_t store = lo;
    for (std::size_t i = lo; i < hi; ++i) {
        if (ops) ops->add();
        if (less(a[i], a[hi])) std::swap(a[i], a[store++]);
    }
    std::swap(a[store], a[hi]);
    return store;
}

template <class T, class Less>
void quicksort_rec(std::vector<T>& a, std::size_t lo, std::size_t hi, Less& less, Pivot pivot, std::mt19937_64& rng,
                   OpCounter* ops) {
    // Recurse on the smaller side and loop on the larger one: stack depth stays O(log n).
    while (lo < hi) {
        if (pivot == Pivot::Random) {
            std::uniform_int_distribution<std::size_t> pick(lo, hi);
            std::swap(a[pick(rng)], a[hi]);
        }
        std::size_t p = partition(a, lo, hi, less, ops);
        if (p - lo < hi - p) {
            if (p > lo) quicksort_rec(a, lo, p - 1, less, pivot, rng, ops);
            lo = p + 1;
        } else {
            if (p < hi) quicksort_rec(a, p + 1, hi, less, pivot, rng, ops);
            if (p == 0) break;
            hi = p - 1;
        }
    }
}
}  // namespace detail

// Quicksort (not stable). Random pivot: expected Theta(n log n) on every input.
// Last-element pivot: Theta(n^2) on sorted or nearly sorted input.
template <class T, class Less>
void quicksort(std::vector<T>& a, Less less, Pivot pivot = Pivot::Random, std::uint64_t seed = 42,
               OpCounter* ops = nullptr) {
    if (a.size() < 2) return;
    std::mt19937_64 rng(seed);
    detail::quicksort_rec(a, 0, a.size() - 1, less, pivot, rng, ops);
}

template <class T>
void quicksort(std::vector<T>& a, Pivot pivot = Pivot::Random, std::uint64_t seed = 42, OpCounter* ops = nullptr) {
    quicksort(a, [](const T& p, const T& q) { return p < q; }, pivot, seed, ops);
}

}  // namespace daa
