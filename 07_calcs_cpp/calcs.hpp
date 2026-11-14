// calcs.hpp — инженерные расчёты: Wood–Armer и послойное суммирование осадки.
// Header-only, C++20. Заготовка под готовое ядро: здесь есть интерфейсы и
// демо с реалистичными формулами. Подставь свои проверенные коэффициенты.
//
// ВАЖНО: формулы ниже — учебные заглушки с правильной размерностью.
// Перед использованием на реальном кейсе сверь с СП 63.13330 (ЖБК)
// и СП 22.13330 (основания и фундаменты).

#pragma once

#include <vector>
#include <cmath>
#include <tuple>
#include <algorithm>
#include <cstddef>

namespace calc {

// ---------- Wood–Armer: расчётные моменты плиты ----------
// Из мембранных усилий mx, my, mxy (кН·м/м) получаем нижнюю и верхнюю
// арматуру: положительные (низ) и отрицательные (верх) моменты по x и y.
struct PlateMoments {
    double mx;   // кН·м/м
    double my;
    double mxy;
};

struct WoodArmer {
    double m_x_bottom;  // нижняя арматура, направление x
    double m_y_bottom;  // нижняя арматура, направление y
    double m_x_top;     // верхняя арматура, направление x
    double m_y_top;     // верхняя арматура, направление y
};

inline WoodArmer wood_armer(const PlateMoments& m) {
    // классика Wood–Armer для изотропной плиты
    double mx_b = m.mx + std::fabs(m.mxy);
    double my_b = m.my + std::fabs(m.mxy);
    double mx_t = m.mx - std::fabs(m.mxy);
    double my_t = m.my - std::fabs(m.mxy);
    return {mx_b, my_b, mx_t, my_t};
}

// Подбор арматуры: площадь на погонный метр из момента M (кН·м/м),
// рабочей высоты d (м), расчётного сопротивления Rs (кПа) и
// сопротивления бетона Rb (кПа). Формула по упрощённому прямоугольному сечению.
inline double steel_area(double M, double d, double Rs, double Rb, double b = 1.0) {
    if (M <= 0.0) return 0.0;
    double am = M / (Rb * b * d * d);
    double xi = 1.0 - std::sqrt(1.0 - 2.0 * am); // относительная высота сжатой зоны
    return xi * Rb * b * d / Rs; // м²/м
}

// ---------- Послойное суммирование осадки ----------
// Осадка по СП 22.13330: s = beta * sum( sigma_zp_i * h_i / E_i ).
// Слои задаются тройками (h — толщина, м; E — модуль деформации, кПа).
// sigma_zp_i — вертикальное напряжение от нагрузки в середине слоя (кПа),
// считается по углу/глубине через простую аппроксимацию (заглушка).
struct Layer {
    double h;  // толщина, м
    double E;  // модуль деформации, кПа
};

inline double settlement(const std::vector<Layer>& layers,
                         double pressure,       // давление под подошвой, кПа
                         double beta = 0.8) {
    double s = 0.0;
    double z = 0.0; // глубина верха слоя от подошвы
    for (const Layer& L : layers) {
        double zmid = z + L.h / 2.0;
        // заглушка: напряжение затухает с глубиной (в реальности — по таблицам alpha)
        double sigma = pressure / (1.0 + zmid / 2.0);
        s += beta * sigma * L.h / L.E;
        z += L.h;
    }
    return s; // метры
}

} // namespace calc
