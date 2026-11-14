// cpm.hpp — сетевой график: топологическая сортировка, прямой/обратный проход,
// критический путь и резервы времени. Header-only, C++20.
//
// Работы задаются списком рёбер: (from -> to, длительность).
// Вершины нумеруются 0..n-1; связи 0..m-1.
// Длительности могут быть детерминированными или случайными (для Монте-Карло).

#pragma once

#include <vector>
#include <algorithm>
#include <limits>
#include <queue>
#include <random>
#include <functional>
#include <stdexcept>

namespace cpm {

struct Result {
    int n;                       // число вершин (событий)
    std::vector<double> es;      // earliest start (прямой проход)
    std::vector<double> lf;      // latest finish (обратный проход)
    std::vector<double> slack;   // резерв события: lf - es
    double duration;             // длина критического пути (срок проекта)
    std::vector<int> topo;       // топологический порядок
    std::vector<int> critical;   // события на критическом пути (slack == 0)
};

// Kahn: топологическая сортировка; кидает invalid_argument, если есть цикл.
inline std::vector<int> topo_sort(int n, const std::vector<std::pair<int,int>>& edges) {
    std::vector<int> indeg(n, 0);
    std::vector<std::vector<int>> g(n);
    for (auto [u, v] : edges) {
        g[u].push_back(v);
        ++indeg[v];
    }
    std::queue<int> q;
    for (int i = 0; i < n; ++i)
        if (indeg[i] == 0) q.push(i);

    std::vector<int> order;
    order.reserve(n);
    while (!q.empty()) {
        int u = q.front(); q.pop();
        order.push_back(u);
        for (int v : g[u])
            if (--indeg[v] == 0) q.push(v);
    }
    if ((int)order.size() != n)
        throw std::invalid_argument("в графе есть цикл — CPM неприменим");
    return order;
}

// Полный расчёт по списку рёбер (u,v,длительность).
inline Result solve(int n,
                    const std::vector<std::tuple<int,int,double>>& edges) {
    std::vector<std::pair<int,int>> eps;
    eps.reserve(edges.size());
    for (auto [u, v, d] : edges) eps.emplace_back(u, v);

    Result r;
    r.n = n;
    r.topo = topo_sort(n, eps);

    std::vector<std::vector<std::pair<int,double>>> g(n); // (куда, длительность)
    for (auto [u, v, d] : edges) g[u].emplace_back(v, d);

    // прямой проход
    r.es.assign(n, 0.0);
    for (int u : r.topo)
        for (auto [v, d] : g[u])
            r.es[v] = std::max(r.es[v], r.es[u] + d);

    r.duration = 0.0;
    for (int i = 0; i < n; ++i) r.duration = std::max(r.duration, r.es[i]);

    // обратный проход
    r.lf.assign(n, r.duration);
    for (int i = n - 1; i >= 0; --i) {
        int u = r.topo[i];
        for (auto [v, d] : g[u])
            r.lf[u] = std::min(r.lf[u], r.lf[v] - d);
    }

    // резервы и критический путь
    r.slack.resize(n);
    for (int i = 0; i < n; ++i) {
        r.slack[i] = r.lf[i] - r.es[i];
        if (r.slack[i] < 1e-9) r.critical.push_back(i);
    }
    return r;
}

// Монте-Карло: длительность каждой работы берётся из генератора.
// Возвращает выборку итоговых сроков проекта.
// dur_gen(edge_index, rng) -> double; вызывается samples * edges.size() раз.
inline std::vector<double> monte_carlo(
        int n,
        const std::vector<std::pair<int,int>>& edges,
        std::function<double(int,std::mt19937&)> dur_gen,
        int samples,
        std::mt19937& rng) {
    std::vector<double> out;
    out.reserve(samples);
    std::vector<std::tuple<int,int,double>> e;
    e.reserve(edges.size());

    for (int s = 0; s < samples; ++s) {
        e.clear();
        for (int i = 0; i < (int)edges.size(); ++i) {
            auto [u, v] = edges[i];
            e.emplace_back(u, v, dur_gen(i, rng));
        }
        out.push_back(solve(n, e).duration);
    }
    return out;
}

// Вероятность уложиться в срок deadline по выборке сроков.
inline double p_finish(const std::vector<double>& samples, double deadline) {
    int ok = 0;
    for (double s : samples) if (s <= deadline) ++ok;
    return static_cast<double>(ok) / static_cast<double>(samples.size());
}

} // namespace cpm
