from prettytable import PrettyTable


def calcular_quimica_solucion(x, materials_data):
    """
    @brief Calcula la química resultante de la solución.
    @param x Lista de variables GEKKO.
    @param materials_data Diccionario con las propiedades de los materiales.
    @return Diccionarios con los valores mínimos y máximos de química estimada de la mezcla para cada elemento.
    """
    solution_chemistry_min = {}
    solution_chemistry_max = {}

    charge_min = materials_data["chemistry"]["min"]
    elementos = list(charge_min.keys())

    peso = sum(x[i].value[0] for i in range(len(x)))

    for j, e in enumerate(elementos):
        solution_chemistry_min[e] = sum(
            x[i].value[0] * materials_data[elementos[i]]['chemistry']['min'].get(e, 0)
            for i in range(len(elementos))
        ) / peso
        solution_chemistry_max[e] = sum(
            x[i].value[0] * materials_data[elementos[i]]['chemistry']['max'].get(e, 0)
            for i in range(len(elementos))
        ) / peso
    return solution_chemistry_min, solution_chemistry_max

def print_resultados_carga(x, materials_data):
    """
    @brief Imprime la composición de la carga y los costos.
    @param x Lista de variables GEKKO.
    @param materials Lista de nombres de materiales.
    @param cost Lista de costos de materiales.
    @param heat_weight Peso objetivo total de la carga (kg).
    """
    print('\nCarga calculada:')
    total_cost = 0
    peso_carga = 0
    materials = list(materials_data.keys())
    for i, mat in enumerate(materials):
        amount = x[i].value[0]
        peso_carga += amount
        total_cost += amount * materials_data[mat]['cost']

    print(f'Peso de la Carga: {peso_carga:.0f} kg ({peso_carga/1000:.3f} tons)')
    print(f'Costo total: ${total_cost:.2f}')
    # Calcular costo por tonelada
    cost_per_ton = total_cost / (peso_carga/1000) if peso_carga/1000 > 0 else 0
    print(f'Costo por tonelada: ${cost_per_ton:.2f}/ton')

def print_table_resultados(x, material_info, alloy_info):
    """
    @brief Imprime la tabla de uso de materiales.

    """
    materials = list(material_info.keys())
    peso = sum(x[i].value[0] for i in range(len(materials)))
    print('\nTabla de materiales:')
    table = PrettyTable()

    table.field_names = ["Material", "Min (kg)", "Value (kg)", "Max (kg)", "Cost", "% Charge"]
    for i, mat in enumerate(materials):
        # Convertir 'min' y 'max' a float si son string con '%'
        min_raw = material_info[mat]['min']
        max_raw = material_info[mat]['max']
        if isinstance(min_raw, str) and '%' in min_raw:
            min_val = float(min_raw.replace('%','')) / 100 * peso
        else:
            min_val = float(min_raw) * peso
        if isinstance(max_raw, str) and '%' in max_raw:
            max_val = float(max_raw.replace('%','')) / 100 * peso
        else:
            max_val = float(max_raw) * peso
        val = x[i].value[0]
        percentage = (val/peso)*100 if peso > 0 else 0
        costo = material_info[mat]['cost'] * val
        table.add_row([mat, f"{min_val:.0f}", f"{val:.0f}", f"{max_val:.0f}", f"{costo:.2f}", f"{percentage:.1f}%"])
    print(table)

def print_quimica_carga(x, materials_data, alloy_data):
   
    print('\nAnálisis químico de la carga:')
    table = PrettyTable()
    table.field_names = ["Element", "Min Spec", "Est. Min", "Est. Max", "Max Spec", "Status"]

    #lista con los elementos quimicos de la aleacion
    elements = list(alloy_data['chemistry']['min'].keys())
    charge_min = alloy_data['chemistry']['min']
    charge_max = alloy_data['chemistry']['max']
    solution_chemistry_min, solution_chemistry_max = calcular_quimica_solucion(x, materials_data)

    for element in elements:
        min_spec = charge_min[element]
        max_spec = charge_max[element]
        est_min = solution_chemistry_min[element]
        est_max = solution_chemistry_max[element]

        tolerance = 1e-6
        min_ok = est_min >= (min_spec - tolerance)
        max_ok = est_max <= (max_spec + tolerance)

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
