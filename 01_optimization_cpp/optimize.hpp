// optimize.hpp — универсальный движок перебора вариантов (header-only, C++20).
//
// Что от тебя нужно (подставь под свой кейс):
//   double score(const T& sol);              — оценка варианта (чем больше, тем лучше)
//   T mutate(const T& sol, std::mt19937& rng); — случайная мутация варианта
//   T random(std::mt19937& rng);             — случайный стартовый вариант
//
// Движок не знает, что лежит в T: это может быть раскладка плитки,
// расстановка кранов, порядок работ, план квартиры — что угодно.
// DOD-стиль: T — struct с непрерывными массивами, а не иерархия классов.

#pragma once

#include <vector>
#include <random>
#include <functional>
#include <algorithm>
#include <cmath>
#include <utility>

namespace opt {

// Восхождение на холм: жадно берём мутацию, если она лучше.
template <typename T, typename ScoreFn, typename MutateFn>
T hill_climb(T init, ScoreFn score, MutateFn mutate, int iterations, std::mt19937& rng) {
    T best = std::move(init);
    double best_score = score(best);
    for (int i = 0; i < iterations; ++i) {
        T cand = mutate(best, rng);
        double s = score(cand);
        if (s > best_score) {
            best = std::move(cand);
            best_score = s;
        }
    }
    return best;
}

// Имитация отжига: принимаем и ухудшения, чтобы выпрыгнуть из локальных минимумов.
// Температура экспоненциально падает от t0 до t1.
template <typename T, typename ScoreFn, typename MutateFn>
T anneal(T init, ScoreFn score, MutateFn mutate, int iterations,
         double t0, double t1, std::mt19937& rng) {
    std::uniform_real_distribution<double> u(0.0, 1.0);
    T best = init;
    T cur = std::move(init);
    double best_score = score(best);
    double cur_score = best_score;

    for (int i = 0; i < iterations; ++i) {
        double frac = static_cast<double>(i) / static_cast<double>(iterations);
        double temp = t0 * std::pow(t1 / t0, frac); // экспоненциальное охлаждение

        T cand = mutate(cur, rng);
        double s = score(cand);
        double d = s - cur_score;
        if (d > 0.0 || u(rng) < std::exp(d / temp)) {
            cur = std::move(cand);
            cur_score = s;
            if (s > best_score) {
                best = cur;
                best_score = s;
            }
        }
    }
    return best;
}

// Простой случайный перебор: базовый бейзлайн, с которым сравнивают всё остальное.
template <typename T, typename ScoreFn, typename RandomFn>
T random_search(ScoreFn score, RandomFn random, int iterations, std::mt19937& rng) {
    T best = random(rng);
    double best_score = score(best);
    for (int i = 1; i < iterations; ++i) {
        T cand = random(rng);
        double s = score(cand);
        if (s > best_score) {
            best = std::move(cand);
            best_score = s;
        }
    }
    return best;
}

} // namespace opt
