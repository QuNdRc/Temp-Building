// Демо для optimize.hpp.
// Кейс: назначить N объектов на M кранов так, чтобы суммарная стоимость
// (расстояние кран->объект) была минимальной, при этом кран не перегружался
// (у каждого крана лимит объектов). Перегруз = штраф.
//
// Сборка:  g++ -O2 -std=c++20 main.cpp -o optimize && ./optimize

#include "optimize.hpp"
#include <iostream>
#include <vector>
#include <numeric>
#include <string>
#include <chrono>

using namespace std;

// ---- Данные задачи (DOD: плоские массивы) ----
struct Problem {
    int objects;          // N
    int cranes;           // M
    vector<double> cost;  // cost[obj * cranes + crane] — стоимость назначения
    int capacity;         // лимит объектов на кран
};

// Решение — плоский массив: assignment[obj] = кран.
struct Solution {
    vector<int> assignment;
};

// ---- score-функция: чем больше, тем лучше (максимизируем) ----
double score(const Solution& s, const Problem& p) {
    vector<int> load(p.cranes, 0);
    double total = 0.0;
    for (int o = 0; o < p.objects; ++o) {
        int c = s.assignment[o];
        total += p.cost[o * p.cranes + c];
        ++load[c];
    }
    double penalty = 0.0;
    for (int c = 0; c < p.cranes; ++c)
        if (load[c] > p.capacity)
            penalty += (load[c] - p.capacity) * 1e4; // жёсткий штраф за перегруз
    return -(total + penalty); // максимизируем отрицательную стоимость
}

Solution random_solution(const Problem& p, mt19937& rng) {
    Solution s;
    s.assignment.resize(p.objects);
    uniform_int_distribution<int> d(0, p.cranes - 1);
    for (auto& a : s.assignment) a = d(rng);
    return s;
}

Solution mutate(const Solution& s, const Problem& p, mt19937& rng) {
    Solution t = s;
    uniform_int_distribution<int> obj(0, p.objects - 1);
    uniform_int_distribution<int> crane(0, p.cranes - 1);
    uniform_real_distribution<double> coin(0.0, 1.0);
    if (coin(rng) < 0.5) {
        // одиночный перенос объекта на другой кран
        t.assignment[obj(rng)] = crane(rng);
    } else {
        // обмен двух объектов местами
        int a = obj(rng), b = obj(rng);
        swap(t.assignment[a], t.assignment[b]);
    }
    return t;
}

int main() {
    Problem p;
    p.objects = 60;
    p.cranes = 5;
    p.capacity = 14;
    mt19937 rng(42);

    // генерируем стоимости (детерминированно для воспроизводимости)
    p.cost.resize(p.objects * p.cranes);
    uniform_real_distribution<double> cost(1.0, 100.0);
    for (auto& c : p.cost) c = cost(rng);

    auto sc = [&](const Solution& s) { return score(s, p); };
    auto mu = [&](const Solution& s, mt19937& r) { return mutate(s, p, r); };
    auto rd = [&](mt19937& r) { return random_solution(p, r); };

    auto t0 = chrono::steady_clock::now();
    Solution rs = opt::random_search<Solution>(sc, rd, 20000, rng);
    Solution hc = opt::hill_climb(random_solution(p, rng), sc, mu, 20000, rng);
    Solution sa = opt::anneal(random_solution(p, rng), sc, mu, 20000, 100.0, 0.1, rng);
    auto t1 = chrono::steady_clock::now();

    auto ms = chrono::duration_cast<chrono::milliseconds>(t1 - t0).count();
    cout << "N=" << p.objects << " объектов, M=" << p.cranes
         << " кранов, лимит=" << p.capacity << "  (" << ms << " ms)\n\n";
    cout << "случайный поиск : " << sc(rs) << "  (стоимость " << -sc(rs) << ")\n";
    cout << "hill climbing   : " << sc(hc) << "  (стоимость " << -sc(hc) << ")\n";
    cout << "simulated anneal: " << sc(sa) << "  (стоимость " << -sc(sa) << ")\n\n";

    // загрузка кранов в лучшем решении
    vector<int> load(p.cranes, 0);
    for (int o = 0; o < p.objects; ++o) ++load[sa.assignment[o]];
    cout << "загрузка кранов в лучшем решении:";
    for (int c = 0; c < p.cranes; ++c) cout << " " << load[c];
    cout << "\n";

    return 0;
}
