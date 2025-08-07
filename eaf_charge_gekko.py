import yaml
from gekko import GEKKO
from prettytable import PrettyTable


# Variable global de depuración - cambiar a True para habilitar mensajes de depuración
DEBUG = False

def normalize_chemistry_value(value):
    """
    @brief Normaliza los valores de química (convierte a fracción decimal de porcentaje en peso).
    @param value Valor de química desde YAML (porcentaje).
    @return Valor como fracción decimal (0-1).
    """
    if value is None:
        return 0.0
    # All chemistry values in YAML are in percentages, divide by 100
    return value / 100.0

def get_val(var):
    """
    @brief Obtiene el valor de una variable GEKKO.
    @param var Variable GEKKO.
    @return Valor como float.
    """
    v = var.value
    try:
        return v[0]
    except (TypeError, IndexError):
        return v

def calc_initial_solution(materials_data, charge_min, charge_max, materials, elements, mat_min, mat_max, heat_weight):
    """
    @brief Encuentra una solución inicial factible usando una composición nominal de carga de acería.
    @param materials_data Diccionario con las propiedades de los materiales.
    @param charge_min Especificación mínima de química.
    @param charge_max Especificación máxima de química.
    @param materials Lista de nombres de materiales.
    @param elements Lista de elementos químicos.
    @param mat_min Porcentaje mínimo para cada material.
    @param mat_max Porcentaje máximo para cada material.
    @param heat_weight Peso objetivo total de la carga (kg).
    @return Lista de valores iniciales para las variables de decisión.
    """
    if DEBUG:
        print("Searching for feasible initial solution using nominal charge...")

    n_materials = len(materials)

    # Composición nominal de carga basada en la práctica de acería
    nominal_composition = {
        'fierro_Primera': 0.2,    # 20%
        'Retornos_CM': 0.35,      # 35%
        'chatarra_CM': 0.44,      # 44%
        'carbon': 0.0,            # 0.0%
        'FeSi75': 0.00          # 0.55%
    }

    # Iniciar con la composición nominal
    initial_x = []
    for i, material in enumerate(materials):
        if material in nominal_composition:
            nominal_amount = nominal_composition[material] * heat_weight
        else:
            # Para materiales que no están en la composición nominal, usar cero
            nominal_amount = 0.0
        initial_x.append(nominal_amount)

    # Normalizar para cumplir la restricción de peso total
    total_weight = sum(initial_x)
    scale_factor = heat_weight / total_weight
    initial_x = [x * scale_factor for x in initial_x]

    # Verificar la factibilidad química con esta solución inicial
    chemistry_feasible = True
    chemistry_violations = []

    for element in elements:
        # Calcular el rango de química para esta solución inicial
        min_chem = sum(initial_x[i] * normalize_chemistry_value(materials_data[materials[i]]['chemistry']['min'].get(element, 0))
                       for i in range(n_materials)) / heat_weight
        max_chem = sum(initial_x[i] * normalize_chemistry_value(materials_data[materials[i]]['chemistry']['max'].get(element, 0))
                       for i in range(n_materials)) / heat_weight

        target_min = normalize_chemistry_value(charge_min[element])
        target_max = normalize_chemistry_value(charge_max[element])

        # Para factibilidad, TODO el rango estimado debe estar dentro del rango objetivo
        if min_chem < target_min or max_chem > target_max:
            chemistry_feasible = False
            chemistry_violations.append(f"{element}: {min_chem*100:.3f}-{max_chem*100:.3f}% vs {target_min*100:.3f}-{target_max*100:.3f}%")

    if chemistry_feasible:
        if DEBUG:
            print("Solución inicial factible encontrada")
    else:
        if DEBUG:
            print("La solución inicial tiene violaciones de química:")
            for violation in chemistry_violations[:3]:  # Mostrar las primeras 3 violaciones
                print(f"   - {violation}")
            if len(chemistry_violations) > 3:
                print(f"   ... y {len(chemistry_violations) - 3} más")

    # Mostrar la composición nominal utilizada
    if DEBUG:
        print("\nComposición inicial nominal:")
        for i, material in enumerate(materials):
            percentage = (initial_x[i] / heat_weight) * 100
            print(f"  {material}: {initial_x[i]:.0f} kg ({initial_x[i]/1000:.2f} tons) ({percentage:.1f}%)")

    # DEBUG: Verificar los cálculos de química para la solución inicial
    if DEBUG:
        print("\nDEBUG - Verificando la química de la solución inicial:")
        for element in elements:
            min_chem = sum(initial_x[i] * normalize_chemistry_value(materials_data[materials[i]]['chemistry']['min'].get(element, 0))
                           for i in range(n_materials)) / heat_weight
            max_chem = sum(initial_x[i] * normalize_chemistry_value(materials_data[materials[i]]['chemistry']['max'].get(element, 0))
                           for i in range(n_materials)) / heat_weight

            target_min = normalize_chemistry_value(charge_min[element])
            target_max = normalize_chemistry_value(charge_max[element])

            print(f"  {element}: {min_chem*100:.3f}-{max_chem*100:.3f}% vs {target_min*100:.3f}-{target_max*100:.3f}%")

    return initial_x

def create_optimization_model(materials_data, charge_info, heat_weight):
    """
    @brief Crea y configura el modelo de optimización.
    @param materials_data Diccionario con la información de los materiales.
    @param charge_info Diccionario con la información de la carga/aleación (incluye min, max, min_acero_pct, max_returns, etc).
    @param heat_weight Peso objetivo total de la carga (kg).
    @return Modelo GEKKO y lista de variables.
    """
    charge_min = charge_info['min']
    charge_max = charge_info['max']
    min_acero_pct = charge_info.get('min_acero_pct', 0.0)
    max_returns = charge_info.get('max_returns', None)
    materials = list(materials_data.keys())
    elements = list(charge_min.keys())
    cost = [materials_data[m]['cost'] for m in materials]
    stock = [materials_data[m]['stock'] for m in materials]
    mat_min = [float(str(materials_data[m]['min']).replace('%',''))/100 for m in materials]
    mat_max = [float(str(materials_data[m]['max']).replace('%',''))/100 for m in materials]

    # Buscar una solución inicial factible
    initial_solution = calc_initial_solution(materials_data, charge_min, charge_max, materials, elements, mat_min, mat_max, heat_weight)

    # Crear modelo GEKKO
    m = GEKKO(remote=False)
    x = [m.Var(value=initial_solution[i], lb=0, ub=stock[i]) for i in range(len(materials))]

    # Restricción: peso total
    m.Equation(sum(x) == heat_weight)

    # Restricción: mínimo de materiales tipo "acero" según min_acero_pct
    acero_indices = [i for i, m_name in enumerate(materials) if materials_data[m_name].get('type', '').lower() == 'acero']
    if acero_indices and min_acero_pct > 0:
        m.Equation(sum(x[i] for i in acero_indices) >= min_acero_pct * heat_weight)

    # Restricción: máximo de materiales tipo "returns" según max_returns
    returns_indices = [i for i, m_name in enumerate(materials) if materials_data[m_name].get('type', '').lower() == 'returns']
    if returns_indices and max_returns is not None:
        m.Equation(sum(x[i] for i in returns_indices) <= max_returns * heat_weight)

    # Restricciones de química para los límites mínimo y máximo de los materiales
    for e in elements:
        min_mix = sum(x[i]*normalize_chemistry_value(materials_data[materials[i]]['chemistry']['min'].get(e,0)) for i in range(len(materials)))/heat_weight
        max_mix = sum(x[i]*normalize_chemistry_value(materials_data[materials[i]]['chemistry']['max'].get(e,0)) for i in range(len(materials)))/heat_weight
        m.Equation(min_mix >= normalize_chemistry_value(charge_min[e]))
        m.Equation(min_mix <= normalize_chemistry_value(charge_max[e]))
        m.Equation(max_mix >= normalize_chemistry_value(charge_min[e]))
        m.Equation(max_mix <= normalize_chemistry_value(charge_max[e]))

    # Restricciones de porcentaje para cada material (lineal)
    for i in range(len(materials)):
        m.Equation(x[i]/heat_weight >= mat_min[i])
        m.Equation(x[i]/heat_weight <= mat_max[i])

    # Objetivo: minimizar el costo
    m.Obj(sum(x[i]*cost[i] for i in range(len(materials))))

    return m, x

def solve_optimization(m, x):
    """
    @brief Resuelve el problema de optimización y retorna el estado y los valores de las variables.
    @param m Objeto modelo GEKKO.
    @param x Lista de variables GEKKO.
    @return (success_flag, x) donde success_flag es True si es factible, False en caso contrario.
    """
    try:
        m.solve(disp=False)  # Deshabilitar salida detallada
        if DEBUG:
            print(f"DEBUG - Estado del solver: {m.options.APPSTATUS}")
        return True, x
    except Exception as e:
        if DEBUG:
            print(f"DEBUG - Excepción durante la resolución: {e}")
            print(f"DEBUG - Estado del solver: {m.options.APPSTATUS}")
        # Retornar valores de variables incluso si es infactible
        return False, x

def calculate_chemistry_solution(x, materials_data, materials, elements, heat_weight):
    """
    @brief Calcula la química resultante de la solución.
    @param x Lista de variables GEKKO.
    @param materials_data Diccionario con las propiedades de los materiales.
    @param materials Lista de nombres de materiales.
    @param elements Lista de elementos químicos.
    @param heat_weight Peso objetivo total de la carga (kg).
    @return Diccionarios con los valores mínimos y máximos de química para cada elemento.
    """
    solution_chemistry_min = {}
    solution_chemistry_max = {}
    for j, e in enumerate(elements):
        # Aplicar normalize_chemistry_value para convertir porcentaje a fracción decimal
        solution_chemistry_min[e] = sum(x[i].value[0]*normalize_chemistry_value(materials_data[materials[i]]['chemistry']['min'].get(e,0)) for i in range(len(materials)))/heat_weight
        solution_chemistry_max[e] = sum(x[i].value[0]*normalize_chemistry_value(materials_data[materials[i]]['chemistry']['max'].get(e,0)) for i in range(len(materials)))/heat_weight

    return solution_chemistry_min, solution_chemistry_max

def print_charge_results(x, materials, cost, heat_weight):
    """
    @brief Imprime la composición de la carga y los costos.
    @param x Lista de variables GEKKO.
    @param materials Lista de nombres de materiales.
    @param cost Lista de costos de materiales.
    @param heat_weight Peso objetivo total de la carga (kg).
    """
    print('\nCarga calculada:')
    total_cost = 0
    for i, mat in enumerate(materials):
        amount = get_val(x[i])
        cost_contribution = amount * cost[i]
        total_cost += cost_contribution
        #print(f"{mat}: {amount:.0f} kg ({amount/1000:.2f} tons) (${cost_contribution:.0f})")
    print(f'Total charge weight: {sum(get_val(x[i]) for i in range(len(materials))):.0f} kg ({sum(get_val(x[i]) for i in range(len(materials)))/1000:.3f} tons)')
    print(f'Total cost: ${total_cost:.2f}')
    # Calcular costo por tonelada
    total_weight_tons = sum(get_val(x[i]) for i in range(len(materials))) / 1000
    cost_per_ton = total_cost / total_weight_tons if total_weight_tons > 0 else 0
    print(f'Cost per ton: ${cost_per_ton:.2f}/ton')

def print_materials_table(materials, mat_min, mat_max, x, cost, heat_weight):
    """
    @brief Imprime la tabla de uso de materiales.
    @param materials Lista de nombres de materiales.
    @param mat_min Porcentaje mínimo para cada material.
    @param mat_max Porcentaje máximo para cada material.
    @param x Lista de variables GEKKO.
    @param cost Lista de costos de materiales.
    @param heat_weight Peso objetivo total de la carga (kg).
    """
    print('\nTabla de materiales:')
    table = PrettyTable()
    table.field_names = ["Material", "Min (kg)", "Value (kg)", "Max (kg)", "Cost", "% Charge"]
    for i, mat in enumerate(materials):
        min_val = mat_min[i]*heat_weight
        val = get_val(x[i])
        max_val = mat_max[i]*heat_weight
        percentage = (val/heat_weight)*100
        table.add_row([mat, f"{min_val:.0f}", f"{val:.0f}", f"{max_val:.0f}", f"{cost[i]:.2f}", f"{percentage:.1f}%"])
    print(table)

def print_chemistry_table(elements, charge_min, charge_max, solution_chemistry_min, solution_chemistry_max):
    """
    @brief Imprime la tabla de análisis químico con especificaciones y valores estimados.
    @param elements Lista de elementos químicos.
    @param charge_min Especificación mínima de química.
    @param charge_max Especificación máxima de química.
    @param solution_chemistry_min Diccionario de química mínima estimada.
    @param solution_chemistry_max Diccionario de química máxima estimada.
    """
    print('\nAnálisis químico de la carga:')
    table = PrettyTable()
    table.field_names = ["Element", "Min Spec", "Est. Min", "Est. Max", "Max Spec", "Status"]
    for element in elements:
        min_spec = charge_min[element]
        max_spec = charge_max[element]
        est_min = solution_chemistry_min[element] * 100
        est_max = solution_chemistry_max[element] * 100

        min_spec_normalized = normalize_chemistry_value(min_spec)
        max_spec_normalized = normalize_chemistry_value(max_spec)
        est_min_normalized = solution_chemistry_min[element]
        est_max_normalized = solution_chemistry_max[element]

        tolerance = 1e-6
        min_ok = est_min_normalized >= (min_spec_normalized - tolerance)
        max_ok = est_max_normalized <= (max_spec_normalized + tolerance)

        status = "OK" if min_ok and max_ok else "Out"
        table.add_row([
            element,
            f"{min_spec:.3f}",
            f"{est_min:.3f}",
            f"{est_max:.3f}",
            f"{max_spec:.3f}",
            status
        ])
    print(table)

def main():
    # Cargar datos de materiales y objetivos desde YAML
    with open('materials.yaml', 'r') as f:
        materials_data = yaml.safe_load(f)
    with open('alloys.yaml', 'r') as f:
        alloys_data = yaml.safe_load(f)

    # Seleccionar la aleación objetivo
    charge_info = alloys_data['cm1']['Carga']

    # Definir el peso objetivo de la carga (puede cambiarse)
    heat_weight = 20000  # kg (20 toneladas)

    # Crear y resolver el modelo de optimización
    m, x = create_optimization_model(materials_data, charge_info, heat_weight)

    # Obtener lista de materiales y elementos para los reportes
    materials = list(materials_data.keys())
    elements = list(charge_info['min'].keys())

    # Obtener costos y límites para los reportes
    cost = [materials_data[m]['cost'] for m in materials]
    mat_min = [float(str(materials_data[m]['min']).replace('%',''))/100 for m in materials]
    mat_max = [float(str(materials_data[m]['max']).replace('%',''))/100 for m in materials]

    # Resolver el modelo
    success, x = solve_optimization(m, x)

    # Mostrar resultados de la optimización
    if success:
        print("Solución óptima encontrada")
    else:
        print("Error de optimización: No se encontró una solución factible")
        print("Mostrando la mejor solución encontrada (puede violar restricciones)")
        print("Sugerencias:")
        print("1. Verifique los rangos de química en alloys.yaml")
        print("2. Aumente el stock disponible de materiales")
        print("3. Relaje las restricciones de porcentaje mínimo/máximo")

    # Calcular la química de la solución (aunque sea infactible)
    solution_chemistry_min, solution_chemistry_max = calculate_chemistry_solution(
        x, materials_data, materials, elements, heat_weight
    )

    # Generar reportes para la mejor solución encontrada
    print_charge_results(x, materials, cost, heat_weight)
    print_materials_table(materials, mat_min, mat_max, x, cost, heat_weight)
    print_chemistry_table(elements, charge_info['min'], charge_info['max'], solution_chemistry_min, solution_chemistry_max)

if __name__ == "__main__":
    main()
