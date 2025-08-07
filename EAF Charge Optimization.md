d) objective finction: minimize the cost of the charge: sum(x_i*c_i)

# Optimización de Carga en Horno Eléctrico de Arco (EAF)

Este documento describe el modelo y la lógica utilizados para optimizar la carga de materiales en un horno eléctrico de arco (EAF), con el objetivo de minimizar el costo total de la carga cumpliendo todas las restricciones metalúrgicas y operativas.

---

## a) Materiales

- Se dispone de un conjunto de **n materiales** (`M_i`), cada uno con:
  - Un **costo por kg** (`C_i`)
  - Un **stock máximo disponible**
  - Un **tipo** (`type`), por ejemplo: `acero`, `returns`, `scrap`, `ferroaleacion`
  - Una **composición química** definida por dos vectores:
    - `MQmin_i`: composición mínima de cada elemento químico
    - `MQmax_i`: composición máxima de cada elemento químico

---

## b) Variables de decisión

- Para cada material `i`, la variable de decisión `x_i` representa la **masa (kg)** de ese material a incluir en la carga.

---

## c) Restricciones

1. **Restricción de química global**  
   - La composición química de la mezcla final debe estar dentro de los límites especificados para cada elemento:
     - Para cada elemento químico, la suma ponderada de los mínimos y máximos de cada material debe estar entre los valores objetivo (`HQmin`, `HQmax`).

2. **Restricción de peso total**
   - La suma de todos los materiales debe ser igual al peso objetivo de la carga:
     - `sum(x_i) = Heat_weight`

3. **Restricción de porcentaje por material**
   - Cada material debe estar dentro de un rango de porcentaje respecto al total de la carga:
     - `MPmin_i <= x_i / sum(x_j) <= MPmax_i`

4. **Restricción de stock**
   - No se puede usar más material del que hay disponible en stock para cada `i`.

5. **Restricción de mínimo de acero**
   - La suma de los pesos de todos los materiales cuyo campo `type` es `acero` debe ser al menos un porcentaje mínimo (`min_acero_pct`) del peso total de la carga.
     - Este valor se define en el archivo de aleaciones (`alloys.yaml`) y puede variar según la aleación objetivo.

6. **Restricción de máximo de returns**
   - La suma de los pesos de todos los materiales cuyo campo `type` es `returns` debe ser menor o igual a un porcentaje máximo (`max_returns`) del peso total de la carga.
     - Este valor también se define en el archivo de aleaciones (`alloys.yaml`).

---

## d) Función objetivo

- **Minimizar el costo total de la carga:**
  - `Costo_total = sum(x_i * C_i)`

---

## e) Datos de entrada

- **materials.yaml:**  
  Define las propiedades de cada material: química, tipo, costo, stock, límites de porcentaje.

- **alloys.yaml:**  
  Define los objetivos de química para la aleación a producir, así como los parámetros `min_acero_pct` y `max_returns` para restricciones adicionales.

---

## f) Salida del programa

- Composición óptima de la carga (kg y % de cada material)
- Costo total y costo por tonelada
- Tabla de uso de materiales (mínimo, máximo, valor óptimo, % de la carga)
- Tabla de análisis químico (especificaciones y valores estimados)
- Mensajes de advertencia si alguna restricción no se puede cumplir

---

## g) Resumen del flujo de solución

1. Se leen los datos de materiales y aleaciones desde archivos YAML.
2. Se genera una solución inicial factible basada en una composición nominal.
3. Se construye y resuelve el modelo de optimización con todas las restricciones.
4. Se reporta la mejor solución encontrada, mostrando composición, costos y cumplimiento de especificaciones.

---