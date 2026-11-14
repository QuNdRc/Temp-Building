// Демо для cpm.hpp.
// Сеть: 8 событий, 10 работ с зависимостями.
// Показываем критический путь, резервы и Монте-Карло: вероятность
// уложиться в директивный срок при разбросе длительностей.
//
// Сборка:  g++ -O2 -std=c++20 main.cpp -o cpm && ./cpm

#include "cpm.hpp"
#include <iostream>
#include <vector>
#include <random>
#include <tuple>
#include <algorithm>

using namespace std;

int main() {
    int n = 8;
    // (from, to, duration)
    vector<tuple<int,int,double>> edges = {
        {0, 1, 4}, {0, 2, 3}, {1, 3, 6}, {2, 3, 5},
        {2, 4, 4}, {3, 5, 7}, {4, 5, 2}, {4, 6, 6},
        {5, 7, 5}, {6, 7, 4},
    };

    auto r = cpm::solve(n, edges);

    cout << "Срок проекта (критический путь): " << r.duration << "\n\n";
    cout << "Топологический порядок:";
    for (int v : r.topo) cout << " " << v;
    cout << "\n\n";

    cout << "Событие | ES | LF | Резерв | Критическое?\n";
    for (int i = 0; i < n; ++i)
        cout << "  " << i << "      | " << r.es[i] << " | " << r.lf[i]
             << " | " << r.slack[i]
             << (r.slack[i] < 1e-9 ? " | ДА" : " | нет") << "\n";

    cout << "\nКритические события:";
    for (int v : r.critical) cout << " " << v;
    cout << "\n\n--- Монте-Карло ---\n";

    // Длительности: треугольное распределение вокруг среднего +- 20%.
    mt19937 rng(123);
    vector<pair<int,int>> eps;
    vector<double> mean;
    for (auto [u, v, d] : edges) { eps.emplace_back(u, v); mean.push_back(d); }

    auto dur_gen = [&](int i, mt19937& r) -> double {
        uniform_real_distribution<double> u(0.0, 1.0);
        double t = u(r);
        // треугольник: min = 0.8*m, max = 1.3*m, мода = m
        double a = 0.8 * mean[i], b = 1.3 * mean[i], m = mean[i];
        double F = (m - a) / (b - a);
        if (t < F) return a + sqrt(t * (b - a) * (m - a));
        else       return b - sqrt((1 - t) * (b - a) * (b - m));
    };

    const int samples = 20000;
    auto times = cpm::monte_carlo(n, eps, dur_gen, samples, rng);
    sort(times.begin(), times.end());

    double deterministic = r.duration;
    cout << "Детерминированный срок: " << deterministic << "\n";
    cout << "Средний срок (MC):      " << times[samples/2] << " (медиана)\n";
    cout << "Минимум / максимум:     " << times.front() << " / " << times.back() << "\n\n";

    // гистограмма вероятностей по 10 корзинам
    cout << "Вероятность уложиться в срок T:\n";
    double lo = times.front(), hi = times.back();
    for (int k = 1; k <= 10; ++k) {
        double T = lo + (hi - lo) * k / 10.0;
        cout << "  T=" << T << " -> " << cpm::p_finish(times, T) * 100.0 << "%\n";
    }

    return 0;
}
