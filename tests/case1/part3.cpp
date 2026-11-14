// Кейс 1, часть 3: график и риски (C++, чистая реализация без внешних библиотек).
//
// Делает по works.csv:
//   1) CPM при likely: критический путь и общий срок;
//   2) Монте-Карло (треугольное распределение min/likely/max), вероятность
//      закончить за 283 дня, >= 10000 прогонов;
//   3) индекс критичности каждой работы + разбиение на 3 группы;
//   4) ресурсное расписание: арм/бет/монт/земл — по одной бригаде,
//      работы одного типа не пересекаются (без прерываний), остальные свободны.
//
// Сборка (MSVC):  cl /std:c++20 /O2 /EHsc part3.cpp /Fe:part3.exe
// Сборка (g++):   g++ -O2 -std=c++20 part3.cpp -o part3
// Запуск:         part3.exe   (работает из tests/case1)

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iostream>
#include <map>
#include <random>
#include <sstream>
#include <string>
#include <vector>

using namespace std;

struct Work {
    string id, name, crew;
    vector<string> preds;
    double mn, likely, mx;
};

// ---- чтение CSV ----
static string strip(const string& s) {
    size_t a = s.find_first_not_of(" \t\r\n\"");
    size_t b = s.find_last_not_of(" \t\r\n\"");
    return (a == string::npos) ? "" : s.substr(a, b - a + 1);
}

static vector<string> split_csv(const string& line) {
    vector<string> out;
    string cur;
    bool in_q = false;
    for (char c : line) {
        if (c == '"') { in_q = !in_q; continue; }
        if (c == ',' && !in_q) { out.push_back(strip(cur)); cur.clear(); continue; }
        cur += c;
    }
    out.push_back(strip(cur));
    return out;
}

static vector<string> split_preds(const string& s) {
    vector<string> out;
    string cur;
    for (char c : s) {
        if (c == ',') { if (!cur.empty()) out.push_back(strip(cur)); cur.clear(); continue; }
        cur += c;
    }
    if (!cur.empty()) out.push_back(strip(cur));
    return out;
}

static vector<Work> read_works(const string& path) {
    ifstream f(path);
    vector<Work> ws;
    string line;
    getline(f, line); // заголовок
    while (getline(f, line)) {
        if (line.empty()) continue;
        auto c = split_csv(line);
        if (c.size() < 7) continue;
        Work w;
        w.id = c[0]; w.name = c[1]; w.preds = split_preds(c[2]);
        w.mn = stod(c[3]); w.likely = stod(c[4]); w.mx = stod(c[5]);
        w.crew = c[6];
        ws.push_back(w);
    }
    return ws;
}

// ---- CPM (детерминированные длительности) ----
struct Cpm {
    int n;
    vector<double> es, ef, ls, lf, tf;
    double total;
    vector<int> critical; // индексы работ на критическом пути
};

static Cpm cpm(const vector<Work>& ws, const vector<double>& dur) {
    int n = (int)ws.size();
    map<string, int> idx;
    for (int i = 0; i < n; ++i) idx[ws[i].id] = i;

    Cpm r; r.n = n;
    r.es.assign(n, 0.0);
    for (int i = 0; i < n; ++i)
        for (auto& p : ws[i].preds)
            r.es[i] = max(r.es[i], r.es[idx[p]] + dur[idx[p]]);

    r.ef.assign(n, 0.0);
    for (int i = 0; i < n; ++i) r.ef[i] = r.es[i] + dur[i];
    r.total = 0.0;
    for (double x : r.ef) r.total = max(r.total, x);

    // обратный проход через successors (CSV задан в топологическом порядке)
    r.lf.assign(n, r.total);
    vector<vector<int>> succ(n);
    for (int j = 0; j < n; ++j)
        for (auto& p : ws[j].preds)
            succ[idx[p]].push_back(j);
    for (int i = n - 1; i >= 0; --i)
        for (int j : succ[i])
            r.lf[i] = min(r.lf[i], r.lf[j] - dur[j]);
    r.ls.assign(n, 0.0);
    r.tf.assign(n, 0.0);
    for (int i = 0; i < n; ++i) {
        r.ls[i] = r.lf[i] - dur[i];
        r.tf[i] = r.ls[i] - r.es[i];
        if (fabs(r.tf[i]) < 1e-9) r.critical.push_back(i);
    }
    return r;
}

// ---- треугольное распределение (min, likely, max) ----
static double triangle(double mn, double likely, double mx, mt19937& rng) {
    uniform_real_distribution<double> u(0.0, 1.0);
    double t = u(rng);
    double F = (likely - mn) / (mx - mn);
    if (t < F) return mn + sqrt(t * (mx - mn) * (likely - mn));
    return mx - sqrt((1.0 - t) * (mx - mn) * (mx - likely));
}

// ---- Монте-Карло: вероятность срока и индекс критичности ----
struct McResult {
    double p_finish_283;
    vector<double> crit_index; // доля прогонов, где полный резерв = 0
};

static McResult monte_carlo(const vector<Work>& ws, int samples, double deadline, mt19937& rng) {
    int n = (int)ws.size();
    vector<int> crit_count(n, 0);
    int finish_ok = 0;
    vector<double> dur(n);
    for (int s = 0; s < samples; ++s) {
        for (int i = 0; i < n; ++i)
            dur[i] = triangle(ws[i].mn, ws[i].likely, ws[i].mx, rng);
        Cpm r = cpm(ws, dur);
        if (r.total <= deadline) ++finish_ok;
        for (int i = 0; i < n; ++i)
            if (fabs(r.tf[i]) < 1e-9) ++crit_count[i];
    }
    McResult out;
    out.p_finish_283 = (double)finish_ok / samples;
    out.crit_index.assign(n, 0.0);
    for (int i = 0; i < n; ++i) out.crit_index[i] = (double)crit_count[i] / samples;
    return out;
}

// ---- п.4: ресурсное расписание (serial SGS) ----
// Ресурсы: арм, бет, монт, земл — capacity 1. Остальные crew не ограничены.
static int res_id(const string& crew) {
    if (crew == "арм") return 0;
    if (crew == "бет") return 1;
    if (crew == "монт") return 2;
    if (crew == "земл") return 3;
    return -1; // без ресурса
}

static double resource_schedule(const vector<Work>& ws) {
    int n = (int)ws.size();
    map<string, int> idx;
    for (int i = 0; i < n; ++i) idx[ws[i].id] = i;
    vector<double> dur(n);
    for (int i = 0; i < n; ++i) dur[i] = ws[i].likely;

    // приоритеты: по ES (из CPM), затем по TF
    Cpm base = cpm(ws, dur);

    vector<int> order(n);
    for (int i = 0; i < n; ++i) order[i] = i;
    stable_sort(order.begin(), order.end(), [&](int a, int b) {
        if (fabs(base.es[a] - base.es[b]) > 1e-9) return base.es[a] < base.es[b];
        return base.tf[a] < base.tf[b]; // критичнее раньше
    });

    vector<double> start(n, -1.0);
    vector<double> free_at(4, 0.0); // когда освободится ресурс типа r
    vector<char> done(n, 0);

    // serial SGS
    for (int step = 0; step < n; ++step) {
        int pick = -1;
        double earliest = 1e18;
        for (int i : order) {
            if (done[i]) continue;
            // все предшественники завершены?
            bool preds_ok = true;
            double t = 0.0;
            for (auto& p : ws[i].preds) {
                int pi = idx[p];
                if (!done[pi]) { preds_ok = false; break; }
                t = max(t, start[pi] + dur[pi]);
            }
            if (!preds_ok) continue;
            // ресурс: если ограниченный, то стартуем не раньше освобождения
            int r = res_id(ws[i].crew);
            if (r >= 0) t = max(t, free_at[r]);
            if (t < earliest - 1e-9) { earliest = t; pick = i; }
        }
        // запланировали pick
        start[pick] = earliest;
        done[pick] = true;
        int r = res_id(ws[pick].crew);
        if (r >= 0) free_at[r] = earliest + dur[pick];
    }

    double makespan = 0.0;
    for (int i = 0; i < n; ++i) makespan = max(makespan, start[i] + dur[i]);
    return makespan;
}

int main(int argc, char** argv) {
    string path = "works.csv";
    if (argc > 1) path = argv[1];

    auto ws = read_works(path);
    int n = (int)ws.size();
    cout << "Работ: " << n << "\n\n";

    // --- п.1 ---
    vector<double> dur(n);
    for (int i = 0; i < n; ++i) dur[i] = ws[i].likely;
    Cpm r = cpm(ws, dur);
    cout << "=== 1) CPM (likely) ===\n";
    cout << "Общий срок: " << r.total << " дней\n";
    cout << "Критический путь: ";
    for (size_t k = 0; k < r.critical.size(); ++k) {
        if (k) cout << " -> ";
        cout << ws[r.critical[k]].id;
    }
    cout << "\n\n";

    // --- п.2 + п.3 ---
    mt19937 rng(20260111);
    const int samples = 20000;
    McResult mc = monte_carlo(ws, samples, 283.0, rng);
    cout << "=== 2) Монте-Карло (" << samples << " прогонов) ===\n";
    cout << "Вероятность закончить за 283 дня: " << mc.p_finish_283 * 100.0 << "%\n\n";

    cout << "=== 3) Индекс критичности ===\n";
    vector<string> always, switching, never;
    for (int i = 0; i < n; ++i) {
        double ci = mc.crit_index[i];
        if (ci >= 0.99) always.push_back(ws[i].id);
        else if (ci >= 0.05) {
            ostringstream ss;
            ss << ws[i].id << "(" << ci << ")";
            switching.push_back(ss.str());
        } else never.push_back(ws[i].id);
    }
    cout << "Всегда критические (>=0.99):";
    for (auto& s : always) cout << " " << s;
    cout << "\nПереключающиеся (0.05..0.99):";
    for (auto& s : switching) cout << " " << s;
    cout << "\nНикогда (<0.05):";
    for (auto& s : never) cout << " " << s;
    cout << "\n\n";

    // --- п.4 ---
    double ms = resource_schedule(ws);
    cout << "=== 4) Ресурсное расписание (likely) ===\n";
    cout << "Срок с ограниченными бригадами: " << ms << " дней\n";
    return 0;
}
