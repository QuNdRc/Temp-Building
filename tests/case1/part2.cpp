// Кейс 1, часть 2: кран + три склада (C++, имитация отжига через optimize.hpp).
//
// Переменные (8 вещественных): центр крана (cx,cy) и левые нижние углы
// трёх складов (арматура 12x6, блоки 14x8, опалубка 10x6).
// score = -cost - штрафы за нарушения. Максимизируем.
//
// Препятствия (здания, деревья, зона ЛЭП) приходят из части 1 (CV).
// Здесь они заданы в секции "ОБСТАНОВКА" и должны быть подставлены из grid.csv.
//
// Сборка (MSVC): cl /std:c++20 /O2 /EHsc part2.cpp /Fe:part2.exe
// Сборка (g++):  g++ -O2 -std=c++20 part2.cpp -o part2
// Запуск:        part2.exe

#include "../../01_optimization_cpp/optimize.hpp"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iostream>
#include <random>
#include <sstream>
#include <string>
#include <vector>

using namespace std;

// ---------- ОБСТАНОВКА (подставить из части 1) ----------
struct Rect { double x, y, w, h; };
struct Circle { double cx, cy, r; };

struct Env {
    double site_w = 140, site_h = 90;
    vector<Rect> new_build = {
        {18, 40, 62, 22},   // корпус 1
        {96, 48, 38, 18},   // корпус 2
    };
    vector<Rect> exist_build = {
        {100, 8, 30, 16},   // существующее здание
    };
    vector<Circle> trees = {
        {10, 20, 3.0}, {14, 31, 3.5}, {30, 9, 3.0}, {86, 28, 3.5}, {88, 36, 3.0},
    };
    // зона ЛЭП: всё, что выше прямой y = 74 + 6*x/140
    double power_y0 = 74, power_slope = 6.0 / 140.0;
    vector<pair<double,double>> lifts_pts = {
        {21,43},{77,43},{21,59},{77,59},{99,51},{131,63}
    };
    double reach = 65;
};

// склад: ширина, высота, trips, lifts, share
struct Store { double w, h, trips, lifts, share; };
static const vector<Store> STORES = {
    {12, 6, 3, 40, 0.6},  // арматура
    {14, 8, 6, 90, 0.5},  // блоки и кирпич
    {10, 6, 2, 30, 0.7},  // опалубка
};

static const double CRANE_W = 6, CRANE_H = 6;
static const double CORP1_X = 49, CORP1_Y = 51;
static const double CORP2_X = 115, CORP2_Y = 57;
static const double GATE_X = 66, GATE_Y = 0;

struct State {
    double cx, cy;             // центр крана
    double sx[3], sy[3];       // левые нижние углы складов
};

// ---------- геометрия ----------
static double dist_point_point(double ax, double ay, double bx, double by) {
    return hypot(ax - bx, ay - by);
}

// минимальное расстояние между прямоугольниками (0 если пересекаются)
static double rect_rect_gap(const Rect& a, const Rect& b) {
    double dx = max(a.x, b.x) - min(a.x + a.w, b.x + b.w);
    double dy = max(a.y, b.y) - min(a.y + a.h, b.y + b.h);
    if (dx <= 0 && dy <= 0) return 0.0;
    if (dx > 0 && dy > 0) return hypot(dx, dy);
    return max(dx, dy);
}

static double rect_circle_gap(double rx, double ry, double rw, double rh,
                              const Circle& c) {
    double nx = max(rx, min(c.cx, rx + rw));
    double ny = max(ry, min(c.cy, ry + rh));
    double d = dist_point_point(c.cx, c.cy, nx, ny);
    return max(0.0, d - c.r);
}

// расстояние от прямоугольника до зоны ЛЭП (полуплоскость выше прямой y = y0 + slope*x)
static double rect_power_gap(double rx, double ry, double rw, double rh,
                             double y0, double slope) {
    // наибольшее превышение над прямой — в левом верхнем углу (прямая растёт вправо)
    double height = (ry + rh) - (y0 + slope * rx);
    if (height >= 0) return 0.0;
    return -height / sqrt(1 + slope * slope);
}

// ---------- score ----------
struct Eval {
    Env env;
    double cost;
    int violations;
};

static double evaluate(const State& s, const Env& env, double& cost_out, int& viol_out) {
    // штрафы
    double penalty = 0;
    int viol = 0;
    auto add_pen = [&](double p) { penalty += p; };

    Rect crane{s.cx - CRANE_W/2, s.cy - CRANE_H/2, CRANE_W, CRANE_H};
    Rect stores[3];
    for (int i = 0; i < 3; ++i)
        stores[i] = {s.sx[i], s.sy[i], STORES[i].w, STORES[i].h};

    // 1. внутри площадки, не ближе 3 м до границы
    const double M = 3;
    if (crane.x < M || crane.y < M || crane.x + crane.w > env.site_w - M ||
        crane.y + crane.h > env.site_h - M) { add_pen(1e6); ++viol; }
    for (int i = 0; i < 3; ++i) {
        Rect& r = stores[i];
        if (r.x < M || r.y < M || r.x + r.w > env.site_w - M ||
            r.y + r.h > env.site_h - M) { add_pen(1e6); ++viol; }
    }

    // 2. зазор до деревьев и ЛЭП >= 1
    for (auto& t : env.trees) {
        if (rect_circle_gap(crane.x, crane.y, crane.w, crane.h, t) < 1) { add_pen(5e5); ++viol; }
        for (int i = 0; i < 3; ++i)
            if (rect_circle_gap(stores[i].x, stores[i].y, stores[i].w, stores[i].h, t) < 1) { add_pen(5e5); ++viol; }
    }
    if (rect_power_gap(crane.x, crane.y, crane.w, crane.h, env.power_y0, env.power_slope) < 1) { add_pen(5e5); ++viol; }
    for (int i = 0; i < 3; ++i)
        if (rect_power_gap(stores[i].x, stores[i].y, stores[i].w, stores[i].h, env.power_y0, env.power_slope) < 1) { add_pen(5e5); ++viol; }

    // 3. кран: >=4 м до новых, >=12 м до существующих; склады: >=1 м до любых зданий
    for (auto& b : env.new_build) {
        if (rect_rect_gap(crane, b) < 4) { add_pen(5e5); ++viol; }
        for (int i = 0; i < 3; ++i)
            if (rect_rect_gap(stores[i], b) < 1) { add_pen(5e5); ++viol; }
    }
    for (auto& b : env.exist_build) {
        if (rect_rect_gap(crane, b) < 12) { add_pen(5e5); ++viol; }
        for (int i = 0; i < 3; ++i)
            if (rect_rect_gap(stores[i], b) < 1) { add_pen(5e5); ++viol; }
    }

    // 4. кран достаёт до всех контрольных точек
    for (auto& p : env.lifts_pts)
        if (dist_point_point(s.cx, s.cy, p.first, p.second) > env.reach) { add_pen(5e5); ++viol; }

    // 5. центр каждого склада в пределах вылета
    for (int i = 0; i < 3; ++i) {
        double scx = s.sx[i] + STORES[i].w/2;
        double scy = s.sy[i] + STORES[i].h/2;
        if (dist_point_point(s.cx, s.cy, scx, scy) > env.reach) { add_pen(5e5); ++viol; }
    }

    // 6. расстояние от склада до основания крана >= 5
    for (int i = 0; i < 3; ++i)
        if (rect_rect_gap(stores[i], crane) < 5) { add_pen(5e5); ++viol; }

    // 7. между складами >= 2
    for (int a = 0; a < 3; ++a)
        for (int b = a + 1; b < 3; ++b)
            if (rect_rect_gap(stores[a], stores[b]) < 2) { add_pen(5e5); ++viol; }

    // ---- стоимость ----
    double cost = 0;
    for (int i = 0; i < 3; ++i) {
        double scx = s.sx[i] + STORES[i].w/2;
        double scy = s.sy[i] + STORES[i].h/2;
        cost += STORES[i].trips * 2 * (fabs(scx - GATE_X) + fabs(scy - GATE_Y));
        double d_target = STORES[i].share * dist_point_point(s.cx, s.cy, CORP1_X, CORP1_Y)
                        + (1 - STORES[i].share) * dist_point_point(s.cx, s.cy, CORP2_X, CORP2_Y);
        cost += STORES[i].lifts * 3 * (dist_point_point(scx, scy, s.cx, s.cy) + d_target) / 10;
    }

    cost_out = cost;
    viol_out = viol;
    return -(cost + penalty); // максимизируем отрицательную (стоимость + штраф)
}

static State random_state(const Env& env, mt19937& rng) {
    uniform_real_distribution<double> cx(3 + CRANE_W/2, env.site_w - 3 - CRANE_W/2);
    uniform_real_distribution<double> cy(3 + CRANE_H/2, env.site_h - 3 - CRANE_H/2);
    State s;
    s.cx = cx(rng); s.cy = cy(rng);
    for (int i = 0; i < 3; ++i) {
        uniform_real_distribution<double> x(3, env.site_w - 3 - STORES[i].w);
        uniform_real_distribution<double> y(3, env.site_h - 3 - STORES[i].h);
        s.sx[i] = x(rng); s.sy[i] = y(rng);
    }
    return s;
}

static State mutate(const State& s, const Env& env, mt19937& rng) {
    State t = s;
    normal_distribution<double> n(0.0, 2.5);
    uniform_real_distribution<double> coin(0, 1);
    if (coin(rng) < 0.3) { // двигаем кран
        t.cx = clamp(t.cx + n(rng), 3 + CRANE_W/2, env.site_w - 3 - CRANE_W/2);
        t.cy = clamp(t.cy + n(rng), 3 + CRANE_H/2, env.site_h - 3 - CRANE_H/2);
    } else { // двигаем один склад
        int i = (int)(rng() % 3);
        t.sx[i] = clamp(t.sx[i] + n(rng), 3.0, env.site_w - 3 - STORES[i].w);
        t.sy[i] = clamp(t.sy[i] + n(rng), 3.0, env.site_h - 3 - STORES[i].h);
    }
    return t;
}

int main() {
    Env env;

    auto sc = [&](const State& s) {
        double c; int v;
        return evaluate(s, env, c, v);
    };
    auto mu = [&](const State& s, mt19937& r) { return mutate(s, env, r); };
    auto rd = [&](mt19937& r) { return random_state(env, r); };

    mt19937 rng(42);
    // несколько рестартов отжига
    State best;
    double best_score = -1e18, best_cost = 0; int best_viol = 0;
    for (int run = 0; run < 8; ++run) {
        State cand = opt::anneal(random_state(env, rng), sc, mu, 200000, 500.0, 0.5, rng);
        double c; int v;
        double sval = evaluate(cand, env, c, v);
        if (sval > best_score) { best_score = sval; best = cand; best_cost = c; best_viol = v; }
    }

    cout << "=== Часть 2: кран и склады ===\n";
    cout << "Кран (центр): (" << best.cx << ", " << best.cy << ")\n";
    const char* names[3] = {"арматура", "блоки и кирпич", "опалубка"};
    for (int i = 0; i < 3; ++i)
        cout << names[i] << ": (" << best.sx[i] << ", " << best.sy[i] << ")\n";
    cout << "Стоимость: " << best_cost << "\n";
    cout << "Нарушений: " << best_viol << "\n";

    return 0;
}
