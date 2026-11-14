// Демо для calcs.hpp: Wood–Armer и осадка.
// Сборка:  cl /std:c++20 /O2 /EHsc main.cpp /Fe:calcs.exe
//          g++ -O2 -std=c++20 main.cpp -o calcs

#include "calcs.hpp"
#include <iostream>
#include <iomanip>

using namespace std;
using namespace calc;

int main() {
    cout << fixed << setprecision(3);

    // --- Wood-Armer ---
    PlateMoments m{45.0, 30.0, 12.0}; // кН·м/м
    auto wa = wood_armer(m);
    cout << "=== Wood-Armer (плита) ===\n";
    cout << "Моменты mx=" << m.mx << ", my=" << m.my << ", mxy=" << m.mxy << "\n";
    cout << "Арматура нижняя: x=" << wa.m_x_bottom << ", y=" << wa.m_y_bottom << " кН·м/м\n";
    cout << "Арматура верхняя: x=" << wa.m_x_top << ", y=" << wa.m_y_top << " кН·м/м\n";

    // Подбор площади арматуры: d=0.14 м, бетон B25 (Rb=14.5 МПа), сталь A500 (Rs=435 МПа)
    double d = 0.14;
    double As = steel_area(wa.m_x_bottom, d, 435000.0, 14500.0);
    cout << "Требуемая арматура по x (низ): " << As * 1e4 << " см2/м\n\n";

    // --- Осадка ---
    cout << "=== Осадка (послойное суммирование) ===\n";
    vector<Layer> layers = {
        {1.0, 12000.0},   // суглинок, E=12 МПа
        {2.0, 18000.0},   // песок, E=18 МПа
        {3.0, 25000.0},   // плотный песок, E=25 МПа
    };
    double pressure = 250.0; // кПа
    double s = settlement(layers, pressure);
    cout << "Давление под подошвой: " << pressure << " кПа\n";
    cout << "Осадка: " << s * 1000.0 << " мм\n";

    return 0;
}
