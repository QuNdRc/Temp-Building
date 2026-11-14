// assignment.hpp — задача назначения (венгерский алгоритм, O(n^3)).
// Header-only, C++20.
//
// Дана матрица cost[n][n] — стоимость назначения работника i на работу j.
// Возвращает назначение: match[i] = j (для строки i назначен столбец j)
// и минимальную суммарную стоимость.
//
// Типичный кейс: распределить бригады/технику по объектам с минимальной
// стоимостью или минимальным временем переброски.

#pragma once

#include <vector>
#include <limits>
#include <algorithm>

namespace assign {

inline std::pair<std::vector<int>, double> hungarian(const std::vector<std::vector<double>>& cost) {
    const int n = (int)cost.size();
    const double inf = std::numeric_limits<double>::infinity();

    std::vector<double> u(n + 1, 0), v(n + 1, 0); // потенциалы
    std::vector<int> p(n + 1, 0), way(n + 1, 0);  // p[j] — строка, way — путь

    for (int i = 1; i <= n; ++i) {
        p[0] = i;
        int j0 = 0;
        std::vector<double> minv(n + 1, inf);
        std::vector<char> used(n + 1, false);
        do {
            used[j0] = true;
            int i0 = p[j0], j1 = 0;
            double delta = inf;
            for (int j = 1; j <= n; ++j) {
                if (used[j]) continue;
                double cur = cost[i0 - 1][j - 1] - u[i0] - v[j];
                if (cur < minv[j]) {
                    minv[j] = cur;
                    way[j] = j0;
                }
                if (minv[j] < delta) {
                    delta = minv[j];
                    j1 = j;
                }
            }
            for (int j = 0; j <= n; ++j) {
                if (used[j]) { u[p[j]] += delta; v[j] -= delta; }
                else { minv[j] -= delta; }
            }
            j0 = j1;
        } while (p[j0] != 0);

        do {
            int j1 = way[j0];
            p[j0] = p[j1];
            j0 = j1;
        } while (j0);
    }

    std::vector<int> match(n);
    double total = 0.0;
    for (int j = 1; j <= n; ++j) {
        if (p[j] != 0) {
            match[p[j] - 1] = j - 1;
            total += cost[p[j] - 1][j - 1];
        }
    }
    return {match, total};
}

} // namespace assign
