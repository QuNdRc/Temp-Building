// Демо для assignment.hpp: распределение 4 бригад на 4 объекта.
// Сборка:  cl /std:c++20 /O2 /EHsc main.cpp /Fe:assignment.exe
//          g++ -O2 -std=c++20 main.cpp -o assignment

#include "assignment.hpp"
#include <iostream>
#include <vector>

using namespace std;

int main() {
    // стоимость (или время переброски) бригады i на объект j
    vector<vector<double>> cost = {
        {10, 19,  8, 15},
        {10, 18,  7, 17},
        {13, 16,  9, 14},
        {12, 19,  8, 18},
    };

    auto [match, total] = assign::hungarian(cost);

    cout << "Бригада -> Объект | Стоимость\n";
    for (int i = 0; i < (int)match.size(); ++i) {
        cout << "  бригада " << i + 1 << " -> объект " << match[i] + 1
             << " | " << cost[i][match[i]] << "\n";
    }
    cout << "Итоговая минимальная стоимость: " << total << "\n";

    return 0;
}
